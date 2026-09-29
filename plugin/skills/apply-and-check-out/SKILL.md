---
name: apply-and-check-out
description: For an agent working on another project that wants to borrow from the Librarian catalogue — check in, find what applies, log what you used, and check out. Use when your primary task is elsewhere and you are consulting the library in passing.
---

# Consulting the library from another project

You are a **Reader**: your primary task is elsewhere. The library is a catalogue of other
people's software and writing, with evidence; it is not a toolkit to lift from.

1. `open_session(purpose="apply", project=..., question=...)`: check in with what you are working
   on and what you need.
2. **find**: `search` for the job to be done (not a product name). Read the Bottom Line and the
   evidence (`get_note`) before relying on a source. Read the result's `verdict`: `uncovered` means
   the library holds nothing that answers it, and `thin` means leads, not answers. Say so
   rather than stretching a weak match.
3. `log_use` for each source you actually used, with what you used it for.
4. **check_out**: `record_application`: what you needed, what you found and took, what it replaced,
   the sources used, and what the library should learn. Then `close_session`.
   If what you learned would help the next reader, `draft_offering` sends a draft to staging for
   the librarian or the person to accept; you never write to the catalogue directly.

Failure posture: return what you found and say what is missing. Do not guess.
