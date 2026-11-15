# Phase 8 model-card candidate — owner review still required

The importer stages changed typed V1 model cards as revisions of the exact matching
provider/model Source. A person accepts them. Source and target hashes detect stale
refreshes; repeated imports do not duplicate a pending or accepted version. Ordinary
V1 imports retain their existing behavior. Generated V1 drafts remain generated;
explicit unclassified authorship does not acquire authority from a folder name.

Accepted owner-created fields take precedence over generated fields, with the shipped
catalogue as fallback. Missing fields fall through; an explicit owner null stays
unknown. The picker and actual route metadata use the same fieldwise merge. Field
authorship/source receipts remain available. A generated card cannot claim owner
authority through its field map. No role is rebound or qualified by these metadata.

Distributor sections in imported model cards are third_party. Explicit reading/personal/
owner/test-note headings retain their author's classification; unmarked sections are
conservatively third_party. Reading a selected distributor section taints the session
at the shared result boundary; reading only owner reading notes does not. Unknown
section labels are unclassified, not trusted. Quoted catalogue results also respect
the existing size cap and actual-route allocation, with omissions reported. Person
access is unaffected.

**Proposed mapping, not applied:** Long_Horizon → tier-1 eligibility only when the
declared context window is at least 1,000,000 tokens, alongside existing tool and
route-qualification checks. Sub_Agent/Coding → tier-2/3 candidates according to the
bounded task; General_Purpose → no automatic tier. This would guide future selections,
not silently change existing bindings. The owner must approve the mapping first.
The picker currently shows the owner class alongside the existing tier recommendation.

The inert `resource-library-expectations.draft.json` is deliberately outside runtime
pack directories. All three records are draft; their effective dialect remains
provider_default. The adjacent review file records their source-card hashes, exact
persisted chat bindings and evidence limitations. These are **not activated**:

- Lead: persisted Seed-2.0-mini; earlier pilot reported the endpoint closed. Not
  rechecked and not replaced here.
- Scribe / inherited research_helper: Gemma-4-26B-A4B-it.
- Clerk: Qwen3.5-397B-A17B. Its reviewed exact reasoning-reserve record already ships;
  keep it and do not activate a duplicate. Its code task still has 1,800 visible tokens.

No matching typed owner card exists for those three bound models in the inspected
10-Models folder. Drafts cite the generated model-card snapshots and disclose that
limitation. The untyped QWEN3.5 file is not promoted to owner metadata from its name.
Owner review and the existing expectation/qualification gates remain necessary before
any new activation. In particular, the generic card-proposal airlock refuses to enable
a non-default dialect from a card alone. OCR's service contract needs separate review;
Kokoro TTS has no chat-token reasoning reserve; STT/embeddings are unconfigured in the
inspected binding store. No source card, setting, personal pack or binding was changed.

The new workspace index uses full-text/local vectors for source documents. Workspace
chunks (including shared hashes) are excluded from hosted embedding estimates, encoder
inputs and loading; hosted workspace queries fall back to lexical search. Local vector
support remains optional. No source code was sent to a hosted embedding service during
these checks: the privacy regression used a mocked encoder.

See the Geo repository's PHASE8_B0 reports for retained first failures and measured
checks. Final woven intake R, the S6 fixture and final full suites remain required
before separate Wave L+B0 merge approvals. Never push or activate these drafts as part
of a merge without the owner's separate instruction.
