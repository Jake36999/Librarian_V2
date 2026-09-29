---
description: Close the current research thread properly
---

Call `session_status`. Close every open brief with what answered it (or that nothing did),
make sure every candidate has a decision, then `close_session` with a summary and the gaps we
could not fill. If anything blocks closing, tell me what it is.
