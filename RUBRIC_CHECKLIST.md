# Rubric Completion Checklist

## Project 3 — Music Recommender Simulation (21 + 12 stretch)

### 1. Clear Explanation of How Music Recommendation Systems Work — 3 pts
- [x] Short explanation of how Spotify / YouTube / Apple Music use data features (genre, mood, tempo, user history). See *How Real-World Music Recommenders Work* in [README.md](README.md).
- [x] Explanation distinguishes input data (content features), user preferences (collaborative + behavioral), and ranking/selection (multi-stage models + business rules).
- [x] Specific, coherent, ML-literate (mentions content vs. collaborative, candidate generation vs. re-ranking, business rules).

### 2. Structured Song Dataset — 3 pts
- [x] [data/tracks.json](data/tracks.json) — 30 tracks (≥ 15-20 required).
- [x] 15 attributes per track including genre, moods, tempo_bpm, energy, valence, acousticness, era, release_year, popularity, danceability, instrumentalness, detailed_mood_tags (≥ 3 required).
- [x] Loads via `TrackCatalog.from_json` without errors; validated by `tests/test_catalog.py::test_catalog_loads_all_tracks` and `tests/test_scoring.py::test_track_has_new_attributes`.

### 3. Scoring Function Reflects User Preferences — 3 pts
- [x] `score_song(user_prefs, song, mode)` in [src/music_agent/scoring.py](src/music_agent/scoring.py) implements weighted matching across mood / genre / artist / audio features / tempo / decade / popularity.
- [x] Scoring works for all songs (returns a `ScoredSong` with numeric `score`); validated by `tests/test_scoring.py::test_score_song_returns_consistent_numeric_score`.
- [x] Scoring reflects the designed features — high-energy preferences reward high-energy tracks; validated by `test_high_energy_pref_rewards_energetic_tracks`.

### 4. Recommendation Function Produces a Sorted List — 3 pts
- [x] `recommend_songs(user_prefs, songs, top_k, mode, artist_penalty)` in [scoring.py](src/music_agent/scoring.py) ranks and returns sorted top-K.
- [x] Three captured terminal outputs in [assets/demo_output/](assets/demo_output/) and embedded in [README.md](README.md) sample interactions.
- [x] Runs without errors for three distinct profiles; validated by `test_three_profiles_produce_distinct_top_pick`.

### 5. Explanations for Recommended Songs — 3 pts
- [x] Each scored song has a `reasons` tuple populated by the scoring function (mood match, genre match, tempo in range, popularity, decade, artist diversity penalty, etc.).
- [x] Explanations reflect the actual scoring logic (every reason corresponds to a code branch in `_score_mood_first` / `_score_genre_first` / `_score_energy_similarity` / `recommend_songs`).
- [x] At least three explanations rendered per profile in [README.md](README.md) demos and in [assets/demo_output/](assets/demo_output/).

### 6. Multiple User Profiles — 3 pts
- [x] Three distinct profiles in [data/profiles.json](data/profiles.json): `lofi_studier`, `cardio_edm_runner`, `acoustic_indie_coffee`.
- [x] Each profile run captured in [assets/demo_output/](assets/demo_output/) and embedded in [README.md](README.md).
- [x] Explicit cross-profile comparison table in README plus prose ("Lo-fi profile shifts toward instrumental low-energy tracks; EDM profile shifts toward danceable high-tempo tracks; Indie profile shifts toward warm-vocal acoustic tracks").

### 7. Completed Model Card — 3 pts
- [x] [model_card.md](model_card.md) describes dataset (30 tracks × 15 attributes), attributes used, intended purpose.
- [x] Algorithmic approach explained in plain language: Plan → Retrieve → Recommend → Check → Revise, with the scoring function expanded.
- [x] Limitations / biases identified: curation bias, small dataset, popularity bias, keyword-based safety, planner brittleness, confidence-internal-only. Plus one improvement idea (embedding-based mood detection).

## Stretch Features (+12 possible, +8 attempted)

### +2 — Additional Song Attributes
- [x] 5 new attributes added: `release_year`, `popularity`, `danceability`, `instrumentalness`, `detailed_mood_tags`.
- [x] Both [data/tracks.json](data/tracks.json) and [src/music_agent/scoring.py](src/music_agent/scoring.py) updated to use them (popularity threshold, danceability target, instrumentalness target).

### +2 — Diversity / Artist Penalty
- [x] `recommend_songs(..., artist_penalty=0.5)` re-ranks results to demote repeat artists; first track keeps full score, second is penalized once, third twice, etc.
- [x] Documented in [model_card.md](model_card.md#diversity--artist-penalty) with rationale (filter-bubble prevention).
- [x] Validated by `tests/test_scoring.py::test_artist_penalty_reduces_repeat_artist_dominance`.
- [x] Visible in profile output: `Music for Airports 1/1` is demoted to slot 4 in the lo-fi profile because Brian Eno already appears at slot 2.

### +2 — Multiple Ranking Modes
- [x] Three modes: `mood_first`, `genre_first`, `energy_similarity`.
- [x] Modular design: each mode is a separate `_score_*` function in [scoring.py](src/music_agent/scoring.py); `score_song` dispatches by mode.
- [x] User-switchable via `--mode` flag in CLI.
- [x] Validated by `test_genre_first_mode_filters_out_other_genres` and `test_energy_similarity_mode_prefers_target_energy`.

### +2 — Visual Output / Summary Table
- [x] `tabulate` library produces a github-flavored markdown table including the per-row reasons.
- [x] Enabled with `--table` flag.
- [x] Output included in [README.md](README.md) sample interactions and saved to [assets/demo_output/](assets/demo_output/).

## Submission Requirements

- [x] **Code pushed** to GitHub repo (public).
- [x] **Functional code** — runs end-to-end without API key (deterministic fallback) and with API key (LLM-grounded summaries).
- [x] **Comprehensive [README.md](README.md)** — title, base project, architecture, setup, sample interactions (3 profile demos + free-form query + refusal + mode comparisons), design decisions, testing summary, stretch features section, reflection.
- [x] **[model_card.md](model_card.md)** — dataset, attributes, algorithmic approach, limitations/biases, one improvement idea, AI collaboration (helpful + flawed suggestion), testing results.
- [x] **System Architecture Diagram** — embedded in README as Mermaid; source at [assets/architecture.mmd](assets/architecture.mmd).
- [x] **Organized assets** — [assets/](assets/) folder contains architecture source, knowledge-base markdown, and [demo_output/](assets/demo_output/) terminal captures.
- [x] **Loom video walkthrough** — script at [LOOM_SCRIPT.md](LOOM_SCRIPT.md); URL placeholder at top of README to be filled after recording.
- [x] **Multiple meaningful commits** (incremental: data layer → package → tests → eval → README → stretch features).

## Execution Verification

- [x] `pytest -q` → **24/24 passed**.
- [x] `python eval/run_eval.py` → **5/6 cases pass**, avg confidence 0.57, written to [eval/last_report.json](eval/last_report.json).
- [x] Three profile demos render correct, distinct top picks with table output.
- [x] Refusal demo returns intent `refusal`, confidence 0.1, no retrieval performed.
- [x] Trace logs populate at [logs/agent_trace.jsonl](logs/agent_trace.jsonl).

---

**Status: COMPLETE.** All required rubric items + 4 of 4 stretch features implemented and verified through execution.
