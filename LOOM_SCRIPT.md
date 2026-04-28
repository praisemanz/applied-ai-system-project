# Loom Walkthrough Script — TuneSage (5–7 minutes)

Use this as the running script for the Loom recording. Total target: ~6 minutes. The video does not need to show installation or file structure — focus on the system running end-to-end.

---

## 0:00 – 0:30 · Hook + What This Is
> "This is TuneSage. It started life as my Module 3 Music Recommender Simulation — a small script that mapped a mood tag to a hard-coded list of songs. I rebuilt it as a full applied AI system: a real curated catalog, a knowledge base, an agentic Plan-Retrieve-Check-Revise loop, RAG over markdown, three ranking modes, an artist-diversity penalty, structured logging, automated tests, and an evaluation harness."
>
> "I'll show three end-to-end runs, the AI features, and the reliability behavior."

## 0:30 – 1:30 · End-to-End Run #1 — Free-Form Query (RAG + Agent)

Run in terminal:
```bash
python -m src.music_agent.cli "calm lo-fi music for studying" --table
```
Talking points while the output renders:
- "The planner extracted moods `focus` and `calm`, set a low target energy, and a tempo range of 60–100 BPM."
- Point at the **table**: "Five tracks, all lo-fi or ambient, all under 100 BPM, all with `focus` or `calm` in the mood tags."
- Point at **Citations**: "These come from two retrieval paths — `moods.md`, `genres.md` are RAG hits; `catalog:t001`, `t006` are the structured catalog. That's the dual-retrieval architecture."
- Point at **Confidence: 0.98** and **Checks passed: True**: "The checker validated that every track was mentioned, no fabricated titles slipped in, and the picks satisfied the `focus`/`calm` slots."

## 1:30 – 2:45 · End-to-End Run #2 — Saved Profile + Mode Switching

Run two profiles back to back:
```bash
python -m src.music_agent.cli --profile cardio_edm_runner --table
python -m src.music_agent.cli --profile acoustic_indie_coffee --table
```
Talking points:
- "Same system, no LLM call needed for these — they go through the public `recommend_songs` API directly."
- Cardio profile: "Top picks are house and pop punk, all over 115 BPM, all popularity ≥ 60. The Daft Punk track gets demoted by the artist-diversity penalty — note the `artist diversity penalty x1` reason on the second Daft Punk entry."
- Acoustic profile: "Completely different result set even though the system is identical: indie folk, bossa nova, neo-soul. That's the scoring function reflecting different `UserPreferences`."

Then switch modes on the same profile:
```bash
python -m src.music_agent.cli --profile lofi_studier --mode genre_first --table
python -m src.music_agent.cli --profile lofi_studier --mode energy_similarity --table
```
- "`genre_first` is a hard filter — only Lo-fi Hip Hop and Ambient survive."
- "`energy_similarity` ignores genre entirely and ranks purely by closeness to target energy. Top results are deep ambient because the target is 0.25."

## 2:45 – 4:00 · AI Feature Behavior Up Close

Open [src/music_agent/agent.py](src/music_agent/agent.py) on the `recommend` method, scroll through:
- "Plan → KB retrieve + Catalog search (parallel) → Recommender → Checker → Reviser if checks fail."
- Open [logs/agent_trace.jsonl](logs/agent_trace.jsonl) — show the JSON lines: `plan`, `kb_retrieve`, `catalog_search`, `draft`, `check`, `final_response`. "Every stage emits a structured trace. This is how I debugged the planner's intent classification."

Open [src/music_agent/scoring.py](src/music_agent/scoring.py):
- "Public scoring API — `score_song` and `recommend_songs`. Three modes. The artist-penalty pass is here, not buried in the agent."

## 4:00 – 5:00 · Reliability + Guardrails

Run the refusal demo:
```bash
python -m src.music_agent.cli "help me hack into Spotify"
```
- Point at **Intent: refusal**, **Confidence: 0.1**, **Checker notes: refused_out_of_scope**: "The disallowed-term filter fires before any retrieval or generation. No tokens are spent on unsafe queries; the trace records `event_type: guardrail`."

Run the eval harness:
```bash
python eval/run_eval.py | tail -20
```
- "Six benchmark cases — five pass, one fails. The failure is the planner brittleness I document in the model card: 'lo-fi' as user shorthand vs. the catalog's exact 'Lo-fi Hip Hop'. Confidence is still 0.95, recommendations are correct — only the intent label is wrong."

Run the test suite:
```bash
pytest -q
```
- "Twenty-four tests, all green: catalog filtering, planner intent detection, three ranking modes, the artist penalty, three-profile sanity check, refusal flow."

## 5:00 – 6:00 · What I Learned + Wrap

> "Three things this project taught me:"
>
> 1. **Routing matters more than generation.** The planner — turning fuzzy human phrasing into structured slots — was the highest-leverage component. Generation was almost a write-once.
> 2. **Hybrid retrieval beats either side alone.** RAG explains *why*; structured scoring filters by hard audio features. Joining them at the recommender stage is the architecture that makes both work.
> 3. **A good checker says no.** The agentic loop's value isn't the LLM call — it's the cheap heuristic checker that runs before output and the one-shot revision that catches over-restrictive filters.
>
> "Code is on GitHub — link in the README. Thanks for watching."

---

## Pre-recording Checklist

- [ ] Terminal font size readable (16 pt+)
- [ ] `logs/agent_trace.jsonl` cleared so the demo writes a fresh trace
- [ ] Editor open to [src/music_agent/agent.py](src/music_agent/agent.py) and [src/music_agent/scoring.py](src/music_agent/scoring.py) on standby tabs
- [ ] `OPENAI_API_KEY` either set (for natural-language summaries) or unset (deterministic fallback) — call out which one in the intro
