# smash-character-competency

Toolkit for exploring Super Smash Bros. player competency through the start.gg GraphQL API. The codebase pulls regional tournament data, stitches together seeds/standings/sets, and surfaces player-level metrics that feed notebooks and visualizations.

## What it does

- Discovers recent tournaments for a state + videogame and caches the raw GraphQL responses locally.
- Normalizes entrant, placement, seed, and per-set character data to build a player-event timeline.
- Computes interpretable metrics (weighted win rates, upset rate, activity, character usage, inferred home state, etc.) that can be printed in the terminal or written to CSV for downstream analysis.
- Powers notebooks/plots (see `Visualizer.ipynb`) that turn the metrics into shareable visuals.

## How the pipeline works

1. `startgg_client.py` authenticates with start.gg (using `STARTGG_API_TOKEN`) and caches responses in `.cache/startgg` to stay within rate limits.
2. `smash_data.py` pages through tournaments, events, seeds, standings, and sets, assembling `PlayerEventResult` records with consistent structure.
3. `metrics.py` aggregates those records into per-player metrics, including optional character-specific splits.
4. `smash_analysis.py` and `run_report.py` tie it together for CLI usage (`generate_player_metrics`), notebooks, or scripted exports.

Because every layer is pure Python, you can import any module from notebooks or other projects without the CLI.

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Export your start.gg API token (create one in the start.gg Developer Portal):

```bash
export STARTGG_API_TOKEN="<your_token_here>"
```

Run the unit tests (they mock out the network layer, so no token needed):

```bash
pytest -q
```

## Running the CLI

```bash
python run_report.py GA --character Marth --months-back 6
```

This command prints a table of the weighted metrics for Georgia Ultimate players in the last six months, highlighting Marth usage. Use `--output /path/to/report.csv` to save the full DataFrame.

### Example output

```
 gamer_tag state home_state home_state_inferred events_played sets_played avg_event_entrants win_rate weighted_win_rate avg_seed_delta opponent_strength character_usage_rate
     Teaser    GA        GA               False            12          58               87    0.66             0.71        -1.8              0.14                 0.32
```

Note: values vary depending on the tournaments in scope.

## CLI flags

`run_report.py` accepts a set of filters to narrow the dataset:

- `state`: Required positional argument. Two-letter code used to discover tournaments.
- `--character`: Target character for usage/weighted metrics (default `Marth`).
- `--videogame-id`: start.gg videogame identifier (Ultimate = `1386`).
- `--months-back`: Rolling tournament discovery window (default `6`).
- `--assume-target-main`: When a player has zero logged sets for the character, treat the target character as their main (assigns win rates from overall performance).
- `--filter-state`: Include only players whose home state (explicit or inferred) matches one of the provided codes. Repeat the flag to allow multiple states.
- `--min-entrants` / `--max-entrants`: Restrict players based on the average size of their events.
- `--start-after`: Drop players whose most recent event started before a specific date (`YYYY-MM-DD`).
- `--output`: Write the full metrics DataFrame to CSV instead of printing a subset of columns.

I may move this section to its own documentation if I add more functionality.

## Working with the metrics elsewhere

- Import `generate_player_metrics` or `generate_character_report` directly to consume DataFrames in notebooks or other scripts.
- Visualizations live in `Visualizer.ipynb`; feel free to generate new plots under `analysis/` and link them here.
- Cached API payloads live under `.cache/startgg`. Delete specific files if you need to bust the cache for a tournament.

## Development tips

- Respect start.gg rate limits; the built-in caching is there to keep repeated runs fast.
- When adding metrics, extend `PlayerAggregate` in `metrics.py` and update the column selection in `run_report.py`.
- If you change GraphQL shapes, update the integration tests under `tests/` to keep the mocked payloads in sync.
