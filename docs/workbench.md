# Source-bound execution and ranking experiments

## Engagements

An engagement binds execution to a catalogued repository and an exact pinned
revision.  An agent may propose or inspect an engagement, but only a person
starts execution.  Closing normally requires an application/outcome record;
force close keeps a reason in the audit trail.

Docker is the only execution mode described as **isolated**.  The workbench
stages revision-pinned source archives into managed named Docker volumes in
the Docker/WSL Linux filesystem.  It never bind-mounts the NTFS vault or
repository.  Containers have read-only source input, separate managed output,
no network, no credentials, no privilege escalation, pinned image hashes, and
explicit CPU/memory/PID/time/output limits.  Results are validated and archived
back into the engagement record.

If Docker Desktop/WSL2 is unavailable, the choices are inspect-only, retry
Docker, or `non_isolated_host_exec`.  The latter needs an extra confirmation
and is never started automatically by an agent.  It uses an ephemeral
workspace, stripped secrets, restricted handles and Job Object limits, but it
does **not** claim network or loopback containment unless a tested Windows
Defender Firewall policy is explicitly active.

## Personal retrieval learning

Learning only creates retrieval-ranking candidates.  It cannot modify model
routing, hosts, permissions, profiles, staging, or promotion.

Candidates begin at 30 valid events / 10 normalized queries (exploratory), and
become recommendable at 75 events / 20 queries.  Benchmark them against held
out questions and scenarios, including quality, coverage, safety,
intent/topic/source-kind slices, and confidence.

The user—not a traffic split—chooses `Current`, `Candidate`, or `Compare`.
Compare shows the same query side by side with rank explanations.  Selections,
feedback context, candidates, benchmark results, and rollbacks are versioned;
**Restore previous ranking** is a single reversible action.

