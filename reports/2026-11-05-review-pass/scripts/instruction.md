You are checking citations. The second file lists CLAIMS that a design review made
about ONE source. The first file is that source's text (a paper, a specification or a
README), as fetched or extracted, possibly with page markers such as [[PDF PAGE 3]] or
[page 3].

For each claim, judge only what the claim attributes to THIS source: what the source
says, shows, measures, proposes or limits. A claim often also contains a design
inference for another system ("Librarian", "proposed transfer", "do not copy ..."). Do
not judge those inferences. Judge only whether the attributed content is faithful.

Verdicts:
- "supported": the source says this, with no material over-claim.
- "partly": the core is right, but a detail is overstated, mis-scoped, or not quite what
  the source says. Say exactly what.
- "unsupported": the source does not say this, or says something different or
  contrary.
- "not_in_text": the attributed content could be in a part of the source not in this
  text (for example only an abstract was available), so it cannot be judged.

Rules:
- Give one or two short verbatim quotes from the SOURCE text for every verdict except
  not_in_text. Copy them exactly, character for character, at most 40 words each. A
  script will check that each quote occurs in the source.
- Give the location: a section name, or the page number from the nearest page marker.
- "note": at most 50 words. For partly or unsupported, state precisely what is wrong.
- Be strict about numbers, scope (benchmark, model, domain), and claims of proof or
  validation.

Answer with ONLY a JSON array, no prose before or after, in this shape:
[{"id": "c1", "verdict": "supported|partly|unsupported|not_in_text",
  "quotes": ["..."], "location": "...", "note": "..."}]
