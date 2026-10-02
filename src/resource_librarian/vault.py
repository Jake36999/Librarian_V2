"""A vault: the user's folder, its layout, and its settings.

The vault is the user's; the system is an installed package. No code lives in
a vault. What the librarian keeps there is split by whether it can be rebuilt:

    .librarian/config.toml     settings (tracked)
    .librarian/sessions/       research threads (tracked; not rebuildable)
    .librarian/queue/          sources logged for intake (tracked)
    .librarian/staging/        proposals awaiting a decision (tracked)
    .librarian/quarantine/     what intake rejected, with the reason (tracked)
    .librarian/eval/           this vault's own retrieval questions and scenarios (tracked)
    .librarian/derived/        index, vectors, extracted text (ignored; delete
                               it and `index` rebuilds it)
    .evidence/                 the data layer, as fetched (tracked, never edited)

V1 kept its staging directory and a primary-data database in ignored folders,
so the only copy of real work sat on one disk. Here only `derived/` is ever
ignored or deleted.
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .rules import Refusal

PROJECT_NAME = re.compile(r"[^A-Za-z0-9 &_.,()'+-]")    # notes.SAFE_NAME's alphabet

NOTE_FOLDERS = ("Projects", "Sources", "Concepts", "Offerings", "Applications",
                "Inbox", "Indexes", "About")
SOURCE_KINDS = ("repository", "paper", "dataset", "document", "page", "standard", "model")
WORK_FOLDERS = ("sessions", "queue", "staging", "quarantine", "eval")
UNFILED = "Unfiled"
TOPIC_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|")

DEFAULT_CONFIG: dict[str, dict[str, Any]] = {
    "vault": {"name": "", "created": "", "format": 2},
    "promotion": {"mode": "person"},
    "usage": {"distribution_posture": "private", "catalogue_role": "reference"},
    "heuristics": {
        # Each of these is corpus-relative and is re-derived by `tune`
        # (THRESHOLD_CARRIES_ITS_DISTRIBUTION). Defaults are V1's measured values.
        "selectivity_ceiling": 0.5,
        "selectivity_min_corpus": 20,
        "rrf_k": 60,
        "concept_threshold": 2,
        "bootstrap_sources": 25,
        "findability_top_k": 5,
        "name_weight": 1.2,
        "coverage_weight": 1.0,
        "vector_weight": 1.0,
        "coverage_min_terms": 2,
        "strong_account": 0.34,
        "thin_account": 0.10,
        "consensus_matches": 2,
        # "union" beat V1's "bm25" order on V1's eval and scenarios, measured
        # 2026-09-25 on a scratch copy of V1's notes (Librarian V2 - M2 Results).
        "coverage_order": "union",
    },
    # Off until the embeddings spike says which model earns its place; see
    # "Librarian V2 - M0 Results". Form: "model2vec:<model id>".
    # `data_shaped`: which sources the `data` intent returns, as axis=value
    # pairs (any one qualifies). A vault decides what counts as data for it.
    "search": {"vectors": "", "data_shaped": ["kind=dataset"]},
    # Scouting: a sweep needs retrieval eval hit@5 of at least `sweep_min_hit`,
    # and stops after `sweep_stop_after` candidates in a row bring nothing new.
    "scout": {"sweep_min_hit": 0.8, "sweep_stop_after": 10},
    # The clerk channel: `provider = "deepinfra"` (or "openai", "lmstudio") is
    # enough; keys are read from the environment, never from this file.
    "clerk": {"provider": ""},
    # Service models (Requirements Addendum R17): jobs with their own request format,
    # chosen in Settings -> Connections and kept per library. OCR (slot 4) reads PDF pages
    # with no text layer - assigned, until a person chooses, the vision-capable model the
    # owner already runs as tier 3. An empty value means none: never a silent fallback.
    "services": {"ocr": "deepinfra:Qwen/Qwen3.5-397B-A17B", "ocr_format": "vision_chat",
                 "tts": "deepinfra:hexgrad/Kokoro-82M"},
    "scribe": {"provider": ""},
}


@dataclass(frozen=True)
class Vault:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root).expanduser().resolve())

    # -- layout ---------------------------------------------------------------
    @property
    def librarian(self) -> Path:
        return self.root / ".librarian"

    @property
    def derived(self) -> Path:
        return self.librarian / "derived"

    @property
    def evidence(self) -> Path:
        return self.root / ".evidence"

    @property
    def config_path(self) -> Path:
        return self.librarian / "config.toml"

    def folder(self, name: str) -> Path:
        return self.root / name

    def source_folder(self, kind: str) -> Path:
        if kind not in SOURCE_KINDS:
            raise ValueError(f"kind {kind!r} is not one of {SOURCE_KINDS}")
        return self.root / "Sources" / kind

    def work(self, name: str) -> Path:
        if name not in WORK_FOLDERS:
            raise ValueError(f"{name!r} is not a work folder")
        return self.librarian / name

    def safe_relative(self, rel: str) -> Path:
        """A path inside the vault that a person would see in Obsidian: no
        dot-folders (the librarian's own state, .obsidian, .git), no escape.
        What the local API's own file routes, and any tool moving or
        attaching a file by a person- or model-given path, resolve against."""
        rel = (rel or "").strip().strip("/").replace("\\", "/")
        parts = [p for p in rel.split("/") if p]
        if any(p.startswith(".") or p == ".." for p in parts):
            raise Refusal("VAULT_REQUIRED", f"{rel!r} is not part of the vault's own notes")
        target = (self.root / "/".join(parts)).resolve()
        if target != self.root and self.root not in target.parents:
            raise Refusal("VAULT_REQUIRED", f"{rel!r} is outside the vault")
        return target

    def project_note(self, name: str) -> Path:
        """`Projects/<name>.md` for a project name as `create_project` writes
        one. A session's `project` is set by whoever opened it, so a name that
        is not already a plain filename (`notes.safe_name`'s alphabet, no
        leading dot) is refused rather than joined into a path - otherwise
        `../../x` walks out of the vault."""
        name = str(name or "").strip()
        if not name or name != PROJECT_NAME.sub("", name).strip(" .") or name.startswith("."):
            plain = name.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".md").strip(" .")
            raise Refusal("VAULT_REQUIRED", f"{name!r} is not a project name: a Project is "
                          f"named by its plain name, never a path"
                          + (f" - {plain!r}" if plain and plain != name else ""))
        return self.root / "Projects" / f"{name}.md"

    def topics(self) -> list[str]:
        """The closed list of topics in `About/Topics.md`: its table's first
        column. A person adds a row to accept a topic; nothing else does."""
        path = self.root / "About" / "Topics.md"
        found: list[str] = []
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                m = TOPIC_ROW.match(line.strip())
                if m and m.group(1).lower() != "topic" and not set(m.group(1)) <= set("-: "):
                    found.append(m.group(1))
        return list(dict.fromkeys(found)) or [UNFILED]

    # -- identity -------------------------------------------------------------
    def exists(self) -> bool:
        return self.config_path.is_file()

    @property
    def title(self) -> str:
        """The library's own name (`[vault] name`), else its folder's. A library made by
        `new-vault.ps1` always lives in a folder named `.librarian-app`, so the folder's
        name alone cannot tell two of them apart."""
        try:
            name = str(self.config().get("vault", {}).get("name") or "").strip()
        except (OSError, ValueError):
            name = ""
        return name or self.root.name

    @classmethod
    def find(cls, start: Path | str | None = None) -> "Vault":
        """The vault containing `start` (default: the current directory)."""
        here = Path(start or Path.cwd()).resolve()
        for candidate in (here, *here.parents):
            if (candidate / ".librarian" / "config.toml").is_file():
                return cls(candidate)
        raise Refusal("VAULT_REQUIRED",
                      f"no vault at or above {here}. Run `init <folder>` to create one.")

    # -- settings -------------------------------------------------------------
    def config(self) -> dict[str, Any]:
        merged = {section: dict(values) for section, values in DEFAULT_CONFIG.items()}
        if self.config_path.is_file():
            with self.config_path.open("rb") as handle:
                for section, values in tomllib.load(handle).items():
                    merged.setdefault(section, {}).update(values if isinstance(values, dict) else {})
        return merged

    def setting(self, section: str, key: str) -> Any:
        return self.config().get(section, {}).get(key)

    def set_setting(self, section: str, key: str, value: str | bool | int | float) -> None:
        """Change one scalar in `config.toml` in place, keeping its comments and
        order; the section or key is added if the file lacks it."""
        rendered = render_config({"_": {key: value}}).splitlines()[-1]
        lines = self.config_path.read_text(encoding="utf-8").splitlines() \
            if self.config_path.is_file() else []
        start = next((i for i, line in enumerate(lines)
                      if line.strip() == f"[{section}]"), None)
        if start is None:
            lines += ["", f"[{section}]", rendered]
        else:
            end = next((i for i in range(start + 1, len(lines))
                        if lines[i].lstrip().startswith("[")), len(lines))
            found = next((i for i in range(start + 1, end)
                          if lines[i].split("=", 1)[0].strip() == key), None)
            if found is None:
                lines.insert(start + 1, rendered)
            else:
                lines[found] = rendered
        self.config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_config(config: dict[str, dict[str, Any]]) -> str:
    """TOML for the handful of scalar types the config uses."""
    def value(v: Any) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return repr(v)
        if isinstance(v, list):
            return "[" + ", ".join(value(i) for i in v) + "]"
        return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'

    lines = ["# Librarian settings for this vault. See About/ for what each means.", ""]
    for section, values in config.items():
        lines.append(f"[{section}]")
        lines += [f"{k} = {value(v)}" for k, v in values.items()]
        lines.append("")
    return "\n".join(lines)


def jsonl_lines(text: str) -> list[str]:
    """The records of a JSON Lines file: only a newline ends one. `json.dumps(...,
    ensure_ascii=False)` leaves U+2028, U+2029, U+0085 and the control separators inside
    a string as they are, and `str.splitlines()` splits on all of them - so it cut one event
    in two (M0, 2026-10-01: a web page's line separator in a research round made the session
    unloadable)."""
    return [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
