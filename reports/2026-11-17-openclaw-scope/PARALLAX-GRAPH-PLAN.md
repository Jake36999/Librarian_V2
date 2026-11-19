# Parallax graph decisions for the next rebuild (2026-11-17)

**Owner's rule:** third-party repositories go on their own graph; anything we built stays on the
internal code graph. A relationship between the two is visible only to someone, person or agent,
who opens both graphs. The OpenClaw presence plugin is not ingested anywhere.

**Graphs, after the rebuild:**
- `Parallax-network_management` is the internal code graph, and stays as it is.
- Third-party repositories go in `Parallax-third-party` when they contain code, or `Parallax-third-party-docs` otherwise.

**Why two third-party graphs:**
- Geo-Grapher keeps one stratum per graph.
- It extracts code only from `.py`, `.js`, `.jsx`, `.ts`, `.tsx` and `.ipynb`; a C, Rust or Go repository is read for its docs alone.
- Measured, and fixed in Geo-Grapher `7c51d23`.

| Folder | Extractable code / files | Now | After |
|---|---|---|---|
| Additional Services/ghostunnel-master | 105 / 6,956 | third-party-docs | **third-party** |
| Additional Services/mitmproxy2swagger-master | 15 / 37 | third-party-docs | **third-party** |
| Additional Services/wazuh-main | 761 / 5,478 | third-party-docs | **third-party** |
| Automated Deployment & Infrastructure/algo-main | 35 / 290 | third-party-docs | **third-party** |
| …/offline_payload/git/RuView | 403 / 1,446 | third-party-docs | **third-party** |
| …/timesketch-master | 422 / 976 | third-party-docs | **third-party** |
| Forensic Logging & Monitoring/third_party_research_latest | 127 / 39,577 | third-party-docs | **third-party** |
| Wi-Fi Sensing & CSI Data Extraction/RuView-main | 405 / 1,453 | third-party-docs | **third-party** |
| third_party_research | 314 / 55,455 | third-party-docs | **third-party** |
| Wi-Fi Sensing & CSI Data Extraction/RTI_Tomography_references | 0 / 6 (archives) | third-party | **third-party-docs** |
| sozu-main, systeminformer-master, linux-80211n-csitool-supplementary (both), ansible-role-ubuntu_autoinstall | 0 | third-party-docs | stays |
| Model_training/docs/external_research_enrichment_data | 72 / 161 | third-party | stays |
| Wi-Fi Sensing & CSI Data Extraction/openclaw-ruview-presence-main | 1 / 9 | third-party-docs | **exclude (owner)** |
| …/offline_payload/git/openclaw-ruview-presence | 1 / 8 | third-party-docs | **exclude (owner)** |

The 6 repositories held for review stay withheld, out of every graph, until the owner decides.

## Notebooks: their own legacy graph (owner, 2026-11-18)

**Owner, 2026-11-18:** the notebooks are pre-2026 drafts that predate quantule_mapper, or packaged
versions of quantule_mapper used to deploy tests on Colab. As source material they are used less
and less, and will eventually be kept only for provenance. Each library gets a separate
`own-legacy` graph (stratum legacy / bronze), so they no longer crowd the live code and docs
graphs, and they stay findable for provenance.

| Library | Folder | Notebooks | Now in | After |
|---|---|---|---|---|
| Nonlinear Field Lab | `docs/legacy_colab_variants_pre-deployment_ R&d` | 63 | quantule_mapper-docs (the 296,905-entity, 18.5 GB graph) | `Nonlinear Field Lab-quantule_mapper-legacy` |
| Nonlinear Field Lab | `colab_jobs/Colab_runs` (packaged Colab runs) | about 6 | quantule_mapper-data | `Nonlinear Field Lab-quantule_mapper-legacy` |
| Resource-Library | DAG Engine `config/landing_pad/veteran` (4 IRER notebooks: 59% of that graph's entities) | 4 | knowledge_compiler_engine (DAG Engine) | `Resource-Library-knowledge_compiler_engine (DAG Engine)-legacy` |
| Resource-Library | DAG Engine `colab_deployment` | 1 | the same | the same legacy graph |

**Not changed:**
- Parallax's notebooks: model training, and third-party examples.
- The 7 notebooks in Nonlinear Field Lab's `docs/transcripts`: transcripts, not code drafts.

**Extraction, measured on the 4 DAG Engine notebooks** (old against new extractor):
- 22,273 → 14,163 entities, 11,549 → 3,439 comment fragments, 18,722 → 4,691 doc-to-code links.
- The 22,342 "candidate" edges from repeated cell names are unchanged. That is the remaining part of audit G1, and moving the notebooks to a legacy graph contains it.

## How it is applied
- One sequence of person-route decisions; the owner gave the instruction in chat on 2026-11-17.
- The decisions change the graph label, or set `exclude` for the two plugin copies.
- That triggers one rebuild with the new extractor (`71c9b85`), which re-extracts every Parallax graph.
- It runs only after the clean-sample benchmark, and then old graph versions are pruned.
