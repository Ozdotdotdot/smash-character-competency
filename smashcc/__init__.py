"""Smash Character Competency core package."""

from .analysis import generate_character_report, generate_player_metrics
from .metrics import compute_player_metrics
from .smash_data import (
    PlayerEventResult,
    SetRecord,
    TournamentFilter,
    collect_player_results_for_tournaments,
    fetch_recent_tournaments,
)
from .startgg_client import StartGGClient

__all__ = [
    "StartGGClient",
    "TournamentFilter",
    "PlayerEventResult",
    "SetRecord",
    "generate_player_metrics",
    "generate_character_report",
    "compute_player_metrics",
    "collect_player_results_for_tournaments",
    "fetch_recent_tournaments",
]
