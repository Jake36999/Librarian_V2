---
name: explore-a-field
description: Explore a field or question in the Librarian vault without a project — map what is held, widen deliberately, and record what was not found. Use when the person asks what exists for an area rather than for a project.
---

# Exploring a field

Open with `open_session(purpose="explore", question=...)`.

- **Frame** the question in the person's words and ask what would disqualify a source
  (`ask_user`); exploring without disqualifiers finds everything and decides nothing.
- **Map** before searching: `search` with `intent: orient`, and note which topics already hold
  material and which hold none.
- **Search** in rounds (`research_round`, then `checkpoint`). When two rounds in a row find
  nothing new, widen: the envelope will suggest outside discovery (`outside: true` on a round
  searches GitHub and arXiv). Outside finds go to staging, never straight into the catalogue.
- **Judge** every candidate; record rejections with reasons.
- A field that turns out to be thin is a result. Say what you looked for and could not find in
  `close_session`'s `gaps`.
