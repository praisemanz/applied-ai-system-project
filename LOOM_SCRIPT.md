# Loom Walkthrough Script — TuneSage (~4:30)

Loom free recordings cap at 5 minutes. This script targets **4:30** and covers exactly what the rubric grades on:

1. End-to-end system run on 2–3 inputs
2. AI feature behavior (RAG + agent + specialization)
3. Reliability / guardrail / evaluation
4. Clear outputs for each case

Spoken lines are in quotes. Stage directions are plain text.

---

## 0:00 – 0:20 · Hook

> "This is TuneSage. The base project was my Module 3 Music Recommender Simulation — a script that mapped a mood tag to a hard-coded list of songs."
>
> "I rebuilt it as a full applied AI system: curated 30-track catalog, RAG over a markdown knowledge base, an agentic Plan-Retrieve-Check-Revise loop, three ranking modes, an artist-diversity penalty, structured logs, and an evaluation harness. Here it is running end-to-end."

## 0:20 – 1:20 · End-to-End Run #1 — Free-Form Query (RAG + Agent)

```bash
python -m src.music_agent.cli "calm lo-fi music for studying" --table
```

While the table renders:

> "The planner pulled out two moods — `focus` and `calm` — set a low target energy, and clamped tempo to 60–100 BPM."

Point at the **table**:

> "Five tracks. Every one is Lo-fi or Ambient, every one is under 100 BPM, every one has `focus` or `calm` in its mood tags."

Point at **Citations**:

> "Two retrieval paths feed the recommender — `moods.md` and `genres.md` from the markdown knowledge base, plus `catalog:t001` and `t006` from the structured catalog. RAG explains *why*; the catalog enforces hard audio features."

Point at **Confidence: 0.95** and **Checks passed: True**:

> "The checker verified every track is real, every one is mentioned in the summary, and the picks satisfy the planner's slots."

## 1:20 – 2:15 · End-to-End Run #2 — Saved Profile + Mode Switch

```bash
python -m src.music_agent.cli --profile cardio_edm_runner --table
```

> "Profiles skip the LLM and go straight through the public scoring API. Top of the table is House and Pop Punk, everything is over 115 BPM, popularity 60 or higher."

Point at the second Daft Punk row:

> "The artist-diversity penalty fired here — that's the `artist diversity penalty x1` reason. Without it, one artist could monopolize the top five."

Now switch ranking mode on the same listener:

```bash
python -m src.music_agent.cli --profile lofi_studier --mode energy_similarity --table
```

> "Same profile, different mode. `energy_similarity` ignores genre completely and ranks by distance to target energy. The target is 0.25, so the top picks are deep ambient — exactly what a content-only fallback would do."

## 2:15 – 3:00 · AI Feature: Agent Trace + Specialization

Open `logs/agent_trace.jsonl`:

> "Every stage of the agent emits a JSON line — `plan`, `kb_retrieve`, `catalog_search`, `draft`, `check`, `final_response`. The whole loop is observable. This is how I debug the planner's intent classification."

Three styles back to back:

```bash
python -m src.music_agent.cli "calm lo-fi music for studying" --style default
python -m src.music_agent.cli "calm lo-fi music for studying" --style studio_notes
python -m src.music_agent.cli "high energy workout playlist for running" --style dj_brief
```

> "Same retrieval, same ranking, three summary styles — that's the specialization layer. Few-shot exemplars for the LLM path, deterministic renderers for the offline path."

Point at the **Style metrics** lines:

> "And the difference is measurable, not just claimed: `dj_brief` is 20 words and uses second person, `studio_notes` is 69 words and bullet-formatted, the default is around 80 words of prose."

## 3:00 – 4:00 · Reliability + Evaluation

Refusal demo:

```bash
python -m src.music_agent.cli "help me hack into Spotify"
```

Point at **Intent: refusal**, **Confidence: 0.1**, **Checker notes: refused_out_of_scope**:

> "The disallowed-term filter fires before any retrieval or generation. Zero tokens spent. The trace logs it as `event_type: guardrail`."

Eval harness:

```bash
python eval/run_eval.py | tail -20
```

> "Eight benchmark cases, seven pass. The one failure is a known planner limitation I document in the model card — the user types `lo-fi`, the planner classifies it as `mood` instead of `genre_and_mood` because the catalog's exact label is `Lo-fi Hip Hop`. Recommendations and confidence are still correct — only the intent label is off."
>
> "The two specialization cases pass. They check the metrics directly — `dj_brief` is at least 20 words shorter than the baseline, and `studio_notes` actually contains bullets."

Test suite:

```bash
pytest -q
```

> "Thirty-three tests, all green — catalog, planner, three ranking modes, artist penalty, three-profile distinctness, refusal, and nine specialization tests."

## 4:00 – 4:30 · Wrap

> "Three takeaways. First, routing matters more than generation — the planner that turns fuzzy phrasing into structured slots was the highest-leverage piece. Second, hybrid retrieval beats either side alone — RAG for *why*, catalog for hard filters. Third, a good checker says no — the cheap heuristic and the one-shot reviser do more for reliability than the LLM call itself."
>
> "Code, model card, and demo outputs are in the repo. Thanks for watching."

---

## Pre-recording Checklist

- [ ] Terminal font size ≥ 16 pt
- [ ] `logs/agent_trace.jsonl` cleared so the demo writes a fresh trace
- [ ] Editor tabs open: `logs/agent_trace.jsonl` (only one you open on camera)
- [ ] `OPENAI_API_KEY` set or unset — either is fine; deterministic fallback covers offline
- [ ] One dry run through every command before recording
