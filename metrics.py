"""
metrics.py
----------

Aggregate player-level metrics from :class:`smash_data.PlayerEventResult`
records. The goal is to produce interpretable axes for visualization while
keeping enough detail for later analysis (e.g., character-only splits).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, Iterable, List, Optional

import pandas as pd

from smash_data import PlayerEventResult, SetRecord


@dataclass
class PlayerAggregate:
    """Mutable accumulator for a player's aggregated metrics."""

    player_id: int
    gamer_tag: str
    state: Optional[str]
    tournaments: set
    events_played: int = 0
    sets_played: int = 0
    wins: int = 0
    weighted_wins: float = 0.0
    weight_sum: float = 0.0
    seed_deltas: List[float] = None
    opponent_strength_values: List[float] = None
    sets_vs_higher_seed: int = 0
    wins_vs_higher_seed: int = 0
    character_sets: int = 0
    character_wins: int = 0
    character_weighted_wins: float = 0.0
    character_weight_sum: float = 0.0
    latest_event_start: int = 0
    event_sizes: List[int] = None
    event_state_counts: Dict[str, int] = None

    def __post_init__(self) -> None:
        self.seed_deltas = self.seed_deltas or []
        self.opponent_strength_values = self.opponent_strength_values or []
        self.event_sizes = self.event_sizes or []
        self.event_state_counts = self.event_state_counts or {}


def _event_weight(event: Dict, now_ts: int) -> float:
    """
    Compute a weight for an event that combines size and recency.
    Larger events get more weight; older events decay exponentially.
    """
    num_entrants = event.get("numEntrants") or 0
    size_weight = math.log2(num_entrants + 1) or 1.0
    start_at = event.get("startAt") or now_ts
    recency_days = max(0, (now_ts - start_at) / 86400)
    recency_weight = math.exp(-recency_days / 90)
    return max(0.1, size_weight * recency_weight)


def _opponent_strength_value(set_record: SetRecord) -> Optional[float]:
    """Convert opponent seed/placement into a normalized strength score."""
    if set_record.opponent_seed:
        return 1.0 / float(set_record.opponent_seed)
    if set_record.opponent_placement:
        return 1.0 / float(set_record.opponent_placement)
    return None


def _uses_target_character(set_record: SetRecord, target_character: str) -> bool:
    target_lower = target_character.lower()
    return any(char.lower() == target_lower for char in set_record.characters)


def _location_state(result: PlayerEventResult) -> Optional[str]:
    location = result.location or {}
    return location.get("state")


def _normalize_state(state: Optional[str]) -> Optional[str]:
    if not state:
        return None
    state = str(state).strip().upper()
    return state or None


def compute_player_metrics(
    player_results: Iterable[PlayerEventResult],
    target_character: str = "Marth",
    assume_target_main: bool = False,
) -> pd.DataFrame:
    """Aggregate metrics for plotting from raw player event results."""
    aggregates: Dict[int, PlayerAggregate] = {}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    for result in player_results:
        agg = aggregates.get(result.player_id)
        if not agg:
            agg = PlayerAggregate(
                player_id=result.player_id,
                gamer_tag=result.gamer_tag,
                state=_location_state(result),
                tournaments=set(),
            )
            aggregates[result.player_id] = agg

        agg.events_played += 1
        tournament_name = result.tournament.get("name")
        if tournament_name:
            agg.tournaments.add(tournament_name)

        if result.seed_num is not None and result.placement is not None:
            agg.seed_deltas.append(float(result.seed_num) - float(result.placement))

        event_weight = _event_weight(result.event, now_ts)
        event_start = result.event.get("startAt")
        if event_start and event_start > agg.latest_event_start:
            agg.latest_event_start = event_start
        event_size = result.event.get("numEntrants")
        if event_size:
            agg.event_sizes.append(int(event_size))
        tournament_state = (result.tournament or {}).get("addrState")
        if tournament_state:
            state_key = _normalize_state(tournament_state)
            if not state_key:
                state_key = "UNKNOWN"
            agg.event_state_counts[state_key] = agg.event_state_counts.get(state_key, 0) + 1

        for set_record in result.sets:
            if set_record.won is None:
                continue
            agg.sets_played += 1
            if set_record.won:
                agg.wins += 1
                agg.weighted_wins += event_weight
            agg.weight_sum += event_weight

            strength = _opponent_strength_value(set_record)
            if strength is not None:
                agg.opponent_strength_values.append(strength)

            if (
                set_record.opponent_seed is not None
                and result.seed_num is not None
                and set_record.opponent_seed < result.seed_num
            ):
                agg.sets_vs_higher_seed += 1
                if set_record.won:
                    agg.wins_vs_higher_seed += 1

            if _uses_target_character(set_record, target_character):
                agg.character_sets += 1
                if set_record.won:
                    agg.character_wins += 1
                    agg.character_weighted_wins += event_weight
                agg.character_weight_sum += event_weight

    rows: List[Dict] = []
    for agg in aggregates.values():
        if agg.sets_played == 0:
            continue

        win_rate = agg.wins / agg.sets_played if agg.sets_played else None
        weighted_win_rate = (
            agg.weighted_wins / agg.weight_sum if agg.weight_sum else None
        )
        avg_seed_delta = mean(agg.seed_deltas) if agg.seed_deltas else None
        opponent_strength = (
            mean(agg.opponent_strength_values)
            if agg.opponent_strength_values
            else None
        )
        avg_event_entrants = (
            mean(agg.event_sizes) if agg.event_sizes else None
        )
        max_event_entrants = max(agg.event_sizes) if agg.event_sizes else None
        total_state_events = sum(agg.event_state_counts.values())
        inferred_state = None
        inferred_state_confidence = None
        if total_state_events:
            top_state, top_count = max(
                agg.event_state_counts.items(),
                key=lambda item: item[1],
            )
            if top_state != "UNKNOWN":
                confidence = top_count / total_state_events
                if confidence > 0.5:
                    inferred_state = top_state
                    inferred_state_confidence = confidence

        explicit_state = _normalize_state(agg.state)
        home_state = explicit_state or inferred_state
        home_state_inferred = explicit_state is None and inferred_state is not None
        home_state_confidence = (
            inferred_state_confidence if home_state_inferred else 1.0 if explicit_state else None
        )

        character_sets = agg.character_sets
        character_win_rate = (
            agg.character_wins / agg.character_sets if agg.character_sets else None
        )
        character_weighted_win_rate = (
            agg.character_weighted_wins / agg.character_weight_sum
            if agg.character_weight_sum
            else None
        )
        character_usage_rate = (
            agg.character_sets / agg.sets_played if agg.sets_played else 0
        )

        if (
            assume_target_main
            and character_sets == 0
            and agg.sets_played > 0
        ):
            character_sets = agg.sets_played
            character_win_rate = win_rate
            character_weighted_win_rate = weighted_win_rate
            character_usage_rate = 1.0

        upset_rate = (
            agg.wins_vs_higher_seed / agg.sets_vs_higher_seed
            if agg.sets_vs_higher_seed
            else None
        )

        activity_score = agg.events_played + 0.1 * agg.sets_played

        rows.append(
            {
                "player_id": agg.player_id,
                "gamer_tag": agg.gamer_tag,
                "state": explicit_state,
                "events_played": agg.events_played,
                "sets_played": agg.sets_played,
                "win_rate": win_rate,
                "weighted_win_rate": weighted_win_rate,
                "avg_seed_delta": avg_seed_delta,
                "opponent_strength": opponent_strength,
                "character_sets": character_sets,
                "character_win_rate": character_win_rate,
                "character_weighted_win_rate": character_weighted_win_rate,
                "character_usage_rate": character_usage_rate,
                "upset_rate": upset_rate,
                "activity_score": activity_score,
                "tournaments_played": len(agg.tournaments),
                "latest_event_start": agg.latest_event_start,
                "avg_event_entrants": avg_event_entrants,
                "max_event_entrants": max_event_entrants,
                "events_with_known_state": total_state_events,
                "inferred_state": inferred_state,
                "inferred_state_confidence": inferred_state_confidence,
                "home_state": home_state,
                "home_state_inferred": home_state_inferred,
                "home_state_confidence": home_state_confidence,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values("weighted_win_rate", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df
