# Model Card — TuneSage Music Recommender

## Overview
**Name:** TuneSage — Agentic Music Recommender with RAG
**Base project:** Module 3 — *Music Recommender Simulation* (`ai110-module3show-musicrecommendersimulation-starter`)
**Purpose:** Turn a free-form mood/genre/artist request *or* a saved listener profile into a short, ranked list of music recommendations with grounded, human-readable explanations.
**Intended users:** Students learning recommender system design, listeners exploring how content-based ranking actually works, and reviewers evaluating an end-to-end applied AI system.

This model card answers the standard reflection prompts (dataset, attributes, algorithmic approach, limitations, biases, AI collaboration, testing).

## Dataset

**Source:** [data/tracks.json](data/tracks.json) — a hand-curated catalog of 30 tracks across 8 genres and 7 decades (1959–2017).

**Per-track attributes (15 fields):**

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Stable identifier (`t001`–`t030`) |
| `title` | string | Track title |
| `artist` | string | Performing artist |
| `genre` | string | One of: Lo-fi Hip Hop, Synthwave, Indie Folk, House, Neo-Soul, Ambient, Pop Punk, Bossa Nova |
| `moods` | tuple[string] | Coarse mood tags (focus, calm, energetic, party, romantic, …) |
| `tempo_bpm` | int | Beats per minute |
| `energy` | float (0–1) | Perceived intensity / loudness |
| `valence` | float (0–1) | Musical positivity |
| `acousticness` | float (0–1) | How acoustic vs. electronic |
| `era` | string | Decade label (`1960s`, `1970s`, …) |
| `release_year` | int | Specific year (added in stretch) |
| `popularity` | int (0–100) | Approximate popularity score (added in stretch) |
| `danceability` | float (0–1) | Rhythmic regularity & beat strength (added in stretch) |
| `instrumentalness` | float (0–1) | 0 = vocal, 1 = no vocals (added in stretch) |
| `detailed_mood_tags` | tuple[string] | Fine-grained tags (`late_night`, `bittersweet`, `cabin`, …) (added in stretch) |
| `description` | string | Short prose summary used in display & RAG |

**Auxiliary knowledge base** ([assets/genres.md](assets/genres.md), [assets/moods.md](assets/moods.md), [assets/artists.md](assets/artists.md)) — curated free-text descriptions used by the RAG component to ground the explanation alongside each recommendation.

**User profiles** ([data/profiles.json](data/profiles.json)) — three pre-built listeners (`lofi_studier`, `cardio_edm_runner`, `acoustic_indie_coffee`) used for end-to-end demos.

## Algorithmic Approach (Plain Language)

TuneSage works in five stages on every request:

1. **Plan.** A keyword-driven planner reads the natural-language query (or loads a saved profile) and produces a structured `UserPreferences` object: favorite genres, favorite moods, favorite artists, target audio features (energy, valence, danceability), tempo range, and decade preferences.
2. **Retrieve.** Two parallel retrievals run on every request:
   - **RAG over the knowledge base** — TF-IDF over `assets/*.md` returns the top genre/mood/artist write-ups so the recommender can *explain* its picks with citations.
   - **Catalog scoring** — every track in `data/tracks.json` is scored against the preferences using one of three modes (see below).
3. **Recommend.** A summary is drafted that ties the ranked tracks to the retrieved knowledge base context. With an OpenAI key, the LLM writes natural language constrained to the ranked tracks; without one, a deterministic template still cites every track and KB chunk.
4. **Check.** A heuristic checker verifies that every ranked track is mentioned in the summary, that no fabricated titles slipped in, that the summary references real KB terms, and that the picks satisfy the planner's mood/genre slots. A confidence score is computed.
5. **Revise.** If checks fail, filters are broadened (over-restrictive genres are dropped) and the summary is regenerated *once*. Then re-checked.

### Scoring Function

The public scoring API is `score_song(user_prefs, song, mode)` and `recommend_songs(user_prefs, songs, top_k, mode, artist_penalty)` in [src/music_agent/scoring.py](src/music_agent/scoring.py).

For each candidate track, the score is a weighted sum of:

- **Mood overlap** — how many of the user's favorite moods appear in the track's mood tags
- **Genre match** — does the track's genre appear in the user's favorite genres
- **Artist match** — does the track's artist appear in the user's favorite artists
- **Audio-feature distance** — `1 - |track.feature - target.feature|` for energy, valence, danceability, acousticness, instrumentalness (each weighted)
- **Tempo bonus / penalty** — track tempo inside / outside the requested range
- **Decade bonus / popularity bonus** — match between user-preferred decades and track era; popularity threshold

The relative weights change per mode:

| Mode | Effect |
| --- | --- |
| `mood_first` (default) | Mood and audio features dominate; genre is a soft bonus. |
| `genre_first` | Hard filter on favorite genres (tracks outside the genre are dropped); mood is a soft bonus. |
| `energy_similarity` | Score driven almost entirely by closeness to `target_energy`; ignores genre / artist. |

### Diversity / Artist Penalty

After scoring, `recommend_songs` re-ranks results to penalize artist repetition. The first track by an artist keeps its full score; the second is reduced by `artist_penalty`, the third by `2 * artist_penalty`, etc. Default penalty is `0.5`. Set `artist_penalty=0` to disable.

This reduces filter-bubble effects: without it, high-affinity profiles (e.g. an EDM runner with no Justice in the catalog but three Daft Punk tracks) would get a top-5 dominated by one artist.

### Specialization (Few-Shot Constrained Tone)

The recommender supports three summary styles via `--style`:

- **`default`** — neutral 3-5 sentence prose explanation (baseline).
- **`dj_brief`** — second-person, ≤ 30 words, ends with a hook question, no first-person pronouns. Designed for in-app radio voiceovers.
- **`studio_notes`** — bullet list, ≤ 90 words, every bullet cites a track or KB chunk, no first-person pronouns. Designed for engineer-facing notes.

**Implementation.**
- Live LLM path uses **few-shot exemplars** ([`build_few_shot_prompt` in `specialization.py`](src/music_agent/specialization.py)). Two synthetic input/output pairs per style are injected into the system prompt with explicit tone rules. The exemplars use *fictitious* track names (`Soft Static`, `Pulse Run`) so the model cannot confuse them with real catalog content.
- Offline (no API key) path uses **constraint-respecting deterministic renderers** (`_render_dj_brief`, `_render_studio_notes`) that hard-enforce word budget, terminator, and bullet structure.
- The checker adapts to each style: `dj_brief` skips the "every track named in summary" check (a 30-word budget can't fit five titles); `studio_notes` skips it too (top-3 highlight format).
- `style_compliance(text, style)` returns a dict with `word_count`, `has_second_person`, `has_first_person`, `has_bullets`, `ends_well`, `compliant`, and `violations`. This is the contract the eval harness uses to assert measurable difference.

**Measurable difference vs. baseline.**

| Metric (lo-fi study query) | `default` | `dj_brief` | `studio_notes` |
| --- | --- | --- | --- |
| Word count | ~80 | **20** | **69** |
| Uses second-person | ✗ | ✓ | ✗ |
| Bullet-formatted | ✗ | ✗ | ✓ |
| Style-compliant per `style_compliance()` | n/a | ✓ | ✓ |
| Word delta from baseline | 0 | **-60** | -11 |

Two eval cases (`specialization_dj_brief_compliance`, `specialization_studio_notes_compliance`) and seven pytest cases (`tests/test_specialization.py`) lock these guarantees. The pytest case `test_styled_output_measurably_differs_from_baseline` asserts the word delta and Jaccard token overlap thresholds in code so regressions are caught automatically.

## Limitations and Biases

**Curation bias.** The 30-track catalog was hand-selected by one person. Genres skew toward Western indie, electronic, and soul styles. There is no representation of country, classical, K-pop, Afrobeat, regional Latin styles, hip hop's mainstream, or non-Western popular music. Mood-to-feature mappings (e.g. "romantic" → high valence + high acousticness) reflect Western listening conventions.

**Small dataset.** With 30 tracks, recall is fragile: niche requests easily produce zero or one match, and the artist-diversity penalty compresses scores quickly. Production deployment would need a catalog 100× larger.

**Popularity bias.** A `min_popularity` filter is supported in the scoring API and used by the EDM runner profile. This intentionally biases toward well-known tracks — acceptable for a workout playlist, but it would systematically de-rank lesser-known artists if applied as a default. The system surfaces the choice in the per-track `reasons` field so users can audit it.

**Keyword-based safety.** The disallowed-term filter (`hack`, `exploit`, `malware`, etc.) is a flat keyword list. It blocks legitimate edge cases (e.g. asking about a band literally called "Hacker") and can be bypassed by creative phrasing. A real deployment needs a classifier-based safety layer.

**Planner brittleness.** Genre detection is exact-string. "Lo-fi" doesn't match the catalog's "Lo-fi Hip Hop", which is the cause of the one failing eval case (`study_focus_request`). Fixing this requires an alias map or a small embedding model.

**Confidence scoring is internal.** The 0.1–0.98 confidence score reflects internal grounding consistency, not real-world fit. A high-confidence recommendation can still be wrong for a specific listener.

### One Improvement Idea

Replace the keyword-based mood detection in [src/music_agent/planner.py](src/music_agent/planner.py) with a small embedding model that maps free-text mood phrases ("zoned-in", "stuck on a deadline") to nearest mood-tag clusters. This would absorb most of the planner's brittleness without changing the rest of the system.

## Testing Results

| Test | Result |
| --- | --- |
| Unit + integration tests (`pytest -q`) | **33 / 33 passed** |
| Eval cases (`python eval/run_eval.py`) | **7 / 8 passed (87.5%)** |
| Average confidence across eval cases | **0.62** |
| Three-profile sanity check | All 3 profiles produce **distinct** top picks (Aruarian Dance / D.A.N.C.E. / Coffee) |
| Specialization compliance (dj_brief, studio_notes) | Both PASS — measurable word/structure delta vs. baseline |

The single failing eval case (`study_focus_request`) is the planner-brittleness limitation above: when the user types "lo-fi" instead of "Lo-fi Hip Hop", intent is classified as `mood` rather than `genre_and_mood` even though the recommendations themselves are correct (confidence 0.95).

## Collaboration with AI

**Helpful suggestion.** When designing the recommender, the AI suggested splitting retrieval into a qualitative path (RAG over `assets/*.md`) and a quantitative path (structured scoring over `data/tracks.json`), then joining only at the recommender stage. This directly led to the dual-retrieval architecture that lets explanations cite real prose ("ambient music prioritizes texture over rhythm") *and* picks be filtered by hard audio features (tempo, energy). I had originally planned a single embedding-based retriever, which would have lost the structured filter.

**Flawed suggestion.** The AI also suggested ranking tracks by cosine similarity over a synthetic "track embedding" built from concatenated mood tags. I implemented a draft and the results were worse than a simple weighted-feature score: tracks with many mood tags dominated the top-K regardless of fit. I rolled the change back and kept the explicit additive scoring in [src/music_agent/scoring.py](src/music_agent/scoring.py), which is both more interpretable and more accurate at this catalog size.

**Pattern observed.** AI suggestions were strongest when shaping *architecture* (clean separation of RAG vs. structured scoring, the agentic Plan/Check/Revise loop) and weakest when proposing *quantitative tricks* (synthetic embeddings, learned weights) for a catalog this small. The takeaway: trust AI for code structure, verify it on numerical claims.

**Second helpful suggestion (specialization).** When I added the constrained-tone styles, the AI proposed splitting the work into a deterministic renderer (offline path) plus few-shot exemplars (live-LLM path), rather than relying on the LLM alone. This was correct: it means the styles work without an API key, the offline output is testable, and the eval harness can assert measurable compliance. Without that split I would have had un-reproducible test results that depended on whether `OPENAI_API_KEY` was set.

**Second flawed suggestion (specialization).** The AI also suggested measuring style difference using only Jaccard token overlap between baseline and styled outputs. I implemented that and it failed for `studio_notes`: bullets and prose share ~70% of their tokens because both list the same track names, artists, BPMs, and genres. I replaced the test with a *structural* assertion (`studio_notes` must contain bullet markers; baseline must not), which catches real differences and ignores spurious lexical overlap. Same lesson as before: trust AI on structure, verify on metrics.

## Reproducibility

```bash
git clone <repo>
cd applied-ai-system-project
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Profile demos
python -m src.music_agent.cli --profile lofi_studier --table
python -m src.music_agent.cli --profile cardio_edm_runner --table
python -m src.music_agent.cli --profile acoustic_indie_coffee --table

# Free-form query
python -m src.music_agent.cli "calm lo-fi music for studying" --table

# Switch ranking modes
python -m src.music_agent.cli --profile lofi_studier --mode energy_similarity --table
python -m src.music_agent.cli --profile lofi_studier --mode genre_first --table

# Specialization (few-shot constrained tone)
python -m src.music_agent.cli "high energy workout playlist for running" --style dj_brief
python -m src.music_agent.cli "calm lo-fi music for studying" --style studio_notes

# Tests + evaluation
pytest -q
python eval/run_eval.py
```

System runs without an API key (deterministic fallback summary) so the entire pipeline is reproducible from a clean clone.
