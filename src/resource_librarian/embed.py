"""Vectors: an optional fourth ranking, cached by content hash.

Off by default. The M0 embeddings spike decides which model, if any, earns
its place (a vector side weaker than lexical pulls fusion *down*), so the
setting is explicit:

    [search]
    vectors = "model2vec:minishlab/potion-base-8M"

**Cost follows the change.** A vector is stored against the chunk's content
hash and the model name. A note re-indexed with unchanged sections re-embeds
nothing; a moved or renamed note keeps its vectors; only new text is embedded.
`sync()` finds exactly the hashes with no vector for this model.

**Deterministic and on the read path.** An embedding model is allowed where a
generative model is not (`READS_NEVER_CALL_A_GENERATIVE_MODEL`): it maps text
to numbers and cannot invent a result.

**Brute force.** Cosine over every chunk is milliseconds up to ~100k chunks;
an approximate index is added only when a measurement asks for one.

Encoders:
- `model2vec:<id>`: static embeddings, pure numpy (the default candidate);
- `fastembed:<id>`: ONNX models, higher quality, heavier;
- `api:<provider>:<id>`: a hosted OpenAI-compatible `/embeddings` model (slot 6, R17);
- `hash:<dim>`: hashed bag of words, needs no download. For tests and as a
  plumbing check only; it is not a semantic model.

**Slot 6 (R17, 2026-09-30).** The model is the library's choice, `[services] embeddings`
(`model2vec:<id>`, or `<provider>:<id>` for a hosted one); the older `[search] vectors` is
still read when that is empty. A hosted model costs money per token, so nothing is embedded
with it until a person starts it (`embed_index`); after that, new text is embedded as it
arrives. Vectors join the ranking only for the intents in `[search] vector_intents`, which a
person sets after `evaluate(compare_vectors=true)` shows where they help.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
import zlib
from typing import Any, Callable, Sequence

from .index import Index

LOCAL_KINDS = ("model2vec", "fastembed", "hash")
API_BATCH = 64

BATCH = 256
TOKEN = re.compile(r"[a-z0-9][a-z0-9_\-]+")


class EncoderUnavailable(RuntimeError):
    pass


def load_encoder(spec: str) -> tuple[str, Callable[[list[str]], Any]]:
    """`kind:model` -> (model name as stored, encode function)."""
    kind, _, model = spec.partition(":")
    try:
        import numpy as np
    except ImportError as exc:
        raise EncoderUnavailable("numpy is not installed") from exc
    if kind == "hash":
        dim = int(model or 256)

        def encode(texts: list[str]):
            out = np.zeros((len(texts), dim), dtype="float32")
            for row, text in enumerate(texts):
                for token in TOKEN.findall(text.lower()):
                    out[row, zlib.crc32(token.encode()) % dim] += 1.0
            return out
        return f"hash:{dim}", encode
    if kind == "model2vec":
        try:
            from model2vec import StaticModel
            loaded = StaticModel.from_pretrained(model)
        except Exception as exc:                            # noqa: BLE001
            raise EncoderUnavailable(f"model2vec {model}: {type(exc).__name__}: {exc}") from exc
        return spec, lambda texts: np.asarray(loaded.encode(list(texts)), dtype="float32")
    if kind == "fastembed":
        try:
            from fastembed import TextEmbedding
            loaded = TextEmbedding(model_name=model)
        except Exception as exc:                            # noqa: BLE001
            raise EncoderUnavailable(f"fastembed {model}: {type(exc).__name__}: {exc}") from exc
        return spec, lambda texts: np.asarray(list(loaded.embed(list(texts))), dtype="float32")
    if kind == "api":
        provider, _, name = model.partition(":")
        post = _api_encoder(provider, name)
        return spec, lambda texts: np.asarray(post(list(texts)), dtype="float32")
    raise EncoderUnavailable(f"unknown encoder {spec!r}; use model2vec:, fastembed:, api: "
                             f"or hash:")


def _api_encoder(provider: str, model: str) -> Callable[[list[str]], list[list[float]]]:
    """A hosted OpenAI-compatible /embeddings endpoint. The key is read at call time."""
    from .providers import PRESETS, _key
    if provider not in PRESETS or PRESETS[provider].get("protocol") != "openai" or not model:
        raise EncoderUnavailable(f"{provider!r} is not an OpenAI-compatible embeddings provider")
    url = PRESETS[provider]["base_url"].rstrip("/") + "/embeddings"
    key_env = PRESETS[provider]["key_env"]

    def post(texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), API_BATCH):
            key = _key(key_env)
            request = urllib.request.Request(
                url, method="POST", data=json.dumps({"model": model, "input":
                                                     texts[start:start + API_BATCH]}).encode(),
                headers={"Content-Type": "application/json",
                         **({"Authorization": f"Bearer {key}"} if key else {})})
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    data = json.loads(response.read())
            except (urllib.error.URLError, TimeoutError) as exc:
                raise EncoderUnavailable(f"{provider}:{model}: {exc}") from exc
            out += [row["embedding"] for row in sorted(data["data"], key=lambda r: r["index"])]
        return out
    return post


def spec_for(vault) -> str:
    """The encoder in use: slot 6's choice, else the older [search] vectors setting."""
    chosen = str(vault.setting("services", "embeddings") or "").strip()
    if chosen:
        kind, _, rest = chosen.partition(":")
        return chosen if kind in LOCAL_KINDS or kind == "api" else f"api:{kind}:{rest}"
    return str(vault.setting("search", "vectors") or "").strip()


def estimate(index: Index, model: str, price_per_1m: float | None = None) -> dict[str, Any]:
    """What embedding the library with `model` would take: the chunks with no vector for it,
    roughly how many tokens, and (for a hosted model whose price is known) the cost."""
    row = index.conn.execute(
        "SELECT COUNT(DISTINCT c.hash) AS n, COALESCE(SUM(LENGTH(c.text)), 0) AS chars "
        "FROM chunk c LEFT JOIN embedding e ON e.hash = c.hash AND e.model = ? "
        "WHERE e.hash IS NULL AND c.role != 'document'", (model,)).fetchone()
    tokens = int(row["chars"] / 4)
    return {"chunks": int(row["n"]), "tokens_est": tokens,
            **({"cost_est_usd": round(tokens / 1e6 * price_per_1m, 4)}
               if price_per_1m is not None else {})}


class VectorSearch:
    def __init__(self, index: Index, model: str, encode: Callable[[list[str]], Any] | None,
                 unavailable: str = ""):
        self.index = index
        self.model = model
        self.encode = encode
        self.unavailable = unavailable
        self._matrix: Any = None
        self._owners: list[str] = []
        self._shapes: list[str] = []
        self._signature: tuple = ()
        # A hosted model embeds nothing until a person has started it once (R17)
        self.hosted = model.startswith("api:")

    def embedded(self) -> int:
        return int(self.index.conn.execute("SELECT COUNT(*) FROM embedding WHERE model = ?",
                                           (self.model,)).fetchone()[0])

    @classmethod
    def from_spec(cls, index: Index, spec: str) -> "VectorSearch":
        try:
            model, encode = load_encoder(spec)
            return cls(index, model, encode)
        except EncoderUnavailable as exc:
            return cls(index, spec, None, f"vectors unavailable ({exc}); search is lexical only")

    # -- writes ---------------------------------------------------------------
    def sync(self) -> int:
        """Embed every chunk whose content has no vector for this model."""
        if self.encode is None:
            return 0
        import numpy as np
        conn = self.index.conn
        missing = conn.execute(
            "SELECT c.hash, MIN(c.heading) AS heading, MIN(c.text) AS text FROM chunk c "
            "LEFT JOIN embedding e ON e.hash = c.hash AND e.model = ? "
            "WHERE e.hash IS NULL GROUP BY c.hash", (self.model,)).fetchall()
        for start in range(0, len(missing), BATCH):
            batch = missing[start:start + BATCH]
            vectors = np.asarray(self.encode([f"{r['heading']}\n{r['text']}" for r in batch]),
                                 dtype="float32")
            norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9
            vectors = vectors / norms
            conn.executemany(
                "INSERT OR REPLACE INTO embedding(hash, model, dim, vector) VALUES (?, ?, ?, ?)",
                [(r["hash"], self.model, int(v.shape[0]), v.tobytes())
                 for r, v in zip(batch, vectors)])
        conn.commit()
        return len(missing)

    def prune(self) -> int:
        """Drop vectors no chunk uses any more (maintenance, not the write path)."""
        cursor = self.index.conn.execute(
            "DELETE FROM embedding WHERE model = ? AND hash NOT IN (SELECT hash FROM chunk)",
            (self.model,))
        self.index.conn.commit()
        return cursor.rowcount

    # -- reads ----------------------------------------------------------------
    def _load(self) -> None:
        import numpy as np
        conn = self.index.conn
        signature = tuple(conn.execute(
            "SELECT COUNT(*), MAX(id) FROM chunk").fetchone()) + tuple(conn.execute(
            "SELECT COUNT(*) FROM embedding WHERE model = ?", (self.model,)).fetchone())
        if signature == self._signature and self._matrix is not None:
            return
        rows = conn.execute(
            "SELECT c.note AS note, n.shape AS shape, e.vector AS vector, e.dim AS dim "
            "FROM chunk c JOIN note n ON n.path = c.path "
            "JOIN embedding e ON e.hash = c.hash AND e.model = ? "
            "WHERE c.role != 'document'", (self.model,)).fetchall()
        self._owners = [r["note"] for r in rows]
        self._shapes = [r["shape"] for r in rows]
        self._matrix = (np.vstack([np.frombuffer(r["vector"], dtype="float32") for r in rows])
                        if rows else np.zeros((0, 1), dtype="float32"))
        self._signature = signature

    def search(self, query: str, shapes: Sequence[str] = ("source",),
               limit: int = 80) -> tuple[list[str], str]:
        """Notes by their best chunk's cosine to the query. Returns (names, why
        not): a non-empty second value means vectors did not contribute."""
        if self.encode is None:
            return [], self.unavailable
        import numpy as np
        if self.hosted and not self.embedded():
            return [], (f"{self.model} is chosen but the library is not embedded yet: a person "
                        f"starts that in Settings -> Connections (slot 6); search is lexical")
        try:
            self.sync()
        except Exception as exc:                            # noqa: BLE001 - a key, a network
            return [], f"vectors unavailable ({str(exc)[:160]}); search is lexical only"
        self._load()
        if not self._owners:
            return [], "no vectors are stored yet"
        q = np.asarray(self.encode([query]), dtype="float32")[0]
        q = q / (np.linalg.norm(q) + 1e-9)
        sims = self._matrix @ q
        allowed = set(shapes)
        best: dict[str, float] = {}
        for i in np.argsort(-sims)[: limit * 8]:
            if self._shapes[i] not in allowed:
                continue
            name = self._owners[i]
            if name not in best:
                best[name] = float(sims[i])
                if len(best) >= limit:
                    break
        return list(best), ""
