"""High-level analytics entry points built on top of the start.gg helpers."""

from typing import Optional

import pandas as pd

from metrics import compute_player_metrics
from smash_data import (
    TournamentFilter,
    collect_player_results_for_tournaments,
    fetch_recent_tournaments,
)
from startgg_client import StartGGClient


def generate_player_metrics(
    state: str = "GA",
    months_back: int = 6,
    videogame_id: int = 1386,
    target_character: str = "Marth",
    use_cache: bool = True,
    assume_target_main: bool = False,
) -> pd.DataFrame:
    """
    Run the full data pipeline and return a DataFrame with per-player metrics.

    Parameters
    ----------
    state:
        Two-letter state code (defaults to Georgia).
    months_back:
        Number of months to look back when discovering tournaments.
    videogame_id:
        start.gg videogame identifier (1386 == Super Smash Bros. Ultimate).
    target_character:
        Character name to derive character-specific metrics (default "Marth").
    use_cache:
        Whether to persist GraphQL responses locally to avoid redundant calls.
    """
    client = StartGGClient(use_cache=use_cache)
    filt = TournamentFilter(
        state=state,
        videogame_id=videogame_id,
        months_back=months_back,
    )
    tournaments = fetch_recent_tournaments(client, filt)
    player_results = collect_player_results_for_tournaments(client, tournaments)
    return compute_player_metrics(
        player_results,
        target_character=target_character,
        assume_target_main=assume_target_main,
    )


def generate_character_report(
    state: str = "GA",
    character: Optional[str] = "Marth",
    months_back: int = 6,
    videogame_id: int = 1386,
    use_cache: bool = True,
    assume_target_main: bool = False,
) -> pd.DataFrame:
    """
    Backwards-compatible wrapper that filters the metrics DataFrame to players
    who primarily use the requested character.
    """
    df = generate_player_metrics(
        state=state,
        months_back=months_back,
        videogame_id=videogame_id,
        target_character=character or "Marth",
        use_cache=use_cache,
        assume_target_main=assume_target_main,
    )
    if df.empty or character is None:
        return df

    mask = df["character_usage_rate"] > 0
    # Only keep players who actually logged sets with the requested character.
    filtered = df[mask].copy()
    filtered.reset_index(drop=True, inplace=True)
    filtered.rename(
        columns={
            "character_sets": f"{character}_sets",
            "character_win_rate": f"{character}_win_rate",
            "character_weighted_win_rate": f"{character}_weighted_win_rate",
            "character_usage_rate": f"{character}_usage_rate",
        },
        inplace=True,
    )
    return filtered


__all__ = [
    "generate_player_metrics",
    "generate_character_report",
]
