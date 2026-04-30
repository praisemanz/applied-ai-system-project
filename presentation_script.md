# TuneSage — 3-minute presentation script

**Total runtime:** ~3:00 at a natural pace (~145 words/minute, ~430 words total).
**Setup before you start:** the Streamlit UI open at `http://localhost:8501`, on the **Discover** tab, query box empty.

---

## [0:00 – 0:20] Hook (≈45 words)

> "Most music recommenders are black boxes. Spotify hands you a playlist, but never tells you *why* a track was picked or what knowledge it used. **TuneSage** flips that. Every recommendation it makes is grounded, cited, and produced by an agentic loop you can watch run, end to end."

*[Show: hero header on the Discover tab.]*

---

## [0:20 – 0:55] Architecture in one breath (≈80 words)

> "Three things work together under the hood. **One** — a Retrieval-Augmented Generation layer over curated genre, mood, and artist write-ups. **Two** — a thirty-track structured catalog with real audio features: tempo, energy, valence, danceability. **Three** — an agentic loop that plans the query, retrieves evidence, scores the catalog, *checks its own draft* for grounding failures, and revises once if it fails. The LLM is optional. Without an API key, deterministic fallbacks produce reproducible output."

*[Show: status pill in sidebar — "LLM mode · live" or "Deterministic mode".]*

---

## [0:55 – 1:35] Demo — free-form query (≈100 words)

> "Let me show it. I'll type *'calm lo-fi music for studying'* and click Recommend."

*[Type query, click Recommend.]*

> "The planner classifies this as a mood intent, retrieves three knowledge-base chunks about focus and lo-fi, scores all thirty tracks with the mood-first ranker, and applies an artist-diversity penalty so a single artist can't dominate the top five."

*[Point to first card.]*

> "Each card shows the tempo, energy, matching mood tags, and the score. Below — a styled summary, citations from `moods.md` and the catalog, a confidence score of 0.95, and *Checks passed: true*."

---

## [1:35 – 2:05] Profiles + Compare (≈70 words)

> "Beyond free-form queries, TuneSage ships three saved listener profiles."

*[Click Profiles tab, then Compare tab.]*

> "Same code, same catalog, completely different output. The Lo-fi Studier averages 69 BPM and energy 0.18. The Cardio Runner — 141 BPM, energy 0.87. The scoring function genuinely reflects each profile's signals — not random shuffling."

---

## [2:05 – 2:30] Specialization + Catalog (≈55 words)

*[Open sidebar, switch Style to `dj_brief`.]*

> "Same query, measurably different summary styles via few-shot exemplars — a thirty-word DJ pitch in second person, or third-person studio-notes bullets. Both compliant with hard rules."

*[Click Catalog tab.]*

> "And the full thirty-track catalog is browsable with genre and energy filters."

---

## [2:30 – 3:00] Reliability + close (≈75 words)

*[Click Trace tab.]*

> "Reliability is built in, not bolted on. Guardrails refuse out-of-scope requests before any retrieval. Every stage of the agentic loop emits a JSON trace — plan, retrieve, score, check, revise — visible right here. Thirty-three unit tests. Eight evaluation cases. Citations on every response."

*[Pause, look up.]*

> "The most important component isn't the LLM. It's the system around it. **That's TuneSage.**"

---

## Speaker notes

- **Pace check:** if you finish each section >5 seconds early, slow down on the Architecture section — don't rush that one.
- **Fallback if the live LLM is unavailable:** the demo still works; just say "running in deterministic mode" when you hit the status pill.
- **If the audience is technical:** swap the closing for *"The LLM is the smallest, most replaceable piece — and that's the point."*
- **One-line elevator version (15 sec):** *"TuneSage is an agentic music recommender that grounds every pick in retrieved evidence, checks its own work, and shows you the trace."*
