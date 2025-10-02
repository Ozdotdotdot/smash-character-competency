"""Analytics helpers for processing Smash data fetched via smash_analytics."""

from typing import Dict, Optional, List, Any

import pandas as pd

import smash_analytics as sa


def compute_win_rate(sets: List[dict], player_id: int) -> float:
    """Compute win rate for the requested player from a list of set payloads."""
    if not sets:
        return 0.0
    wins = sum(1 for s in sets if s.get("winnerId") == player_id)
    return wins / len(sets)


def extract_main_character(
    sets: List[dict],
    player_id: int,
    character_lookup: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Infer the most frequently selected character for the player across games."""
    char_counts: Dict[str, int] = {}
    for s in sets:
        player_entrant_ids = set()
        for slot in s.get("slots", []) or []:
            entrant = slot.get("entrant") or {}
            for participant in entrant.get("participants", []) or []:
                player = participant.get("player") or {}
                if player.get("id") == player_id:
                    entrant_id = entrant.get("id")
                    if entrant_id:
                        player_entrant_ids.add(entrant_id)
        if not player_entrant_ids:
            continue
        for g in s.get("games", []) or []:
            for sel in g.get("selections", []) or []:
                selection_type = (sel.get("selectionType") or "").upper()
                if selection_type and selection_type != "CHARACTER":
                    continue
                entrant = sel.get("entrant") or {}
                if entrant.get("id") not in player_entrant_ids:
                    continue
                char_info = sel.get("character") or {}
                char = char_info.get("name")
                if not char and character_lookup:
                    selection_value = sel.get("selectionValue")
                    if selection_value is not None:
                        key_candidates = [str(selection_value)]
                        if isinstance(selection_value, (int, float)):
                            key_candidates.append(str(int(selection_value)))
                        for key in key_candidates:
                            char = character_lookup.get(key)
                            if char:
                                break
                if char:
                    char_counts[char] = char_counts.get(char, 0) + 1
    if not char_counts:
        return None
    return max(char_counts, key=char_counts.get)


def generate_character_report(
    state: str,
    character: Optional[str] = None,
    videogame_id: int = 1386,
    per_page_tournaments: int = 3,
    per_page_entrants: int = 10,
    per_page_sets: int = 10,
    include_without_character: bool = False,
) -> pd.DataFrame:
    """Generate a filtered DataFrame of players in a state using raw API payloads."""
    character_lookup = sa.get_character_map(videogame_id)
    records = sa.fetch_state_player_records(
        state,
        videogame_id=videogame_id,
        per_page_tournaments=per_page_tournaments,
        per_page_entrants=per_page_entrants,
        per_page_sets=per_page_sets,
    )
    rows: List[Dict[str, Any]] = []
    normalized_target = character.lower() if isinstance(character, str) else None

    for record in records:
        player = record.get("player") or {}
        player_id = player.get("id")
        if not player_id:
            continue
        sets = record.get("sets") or []
        win_rate = compute_win_rate(sets, player_id)
        main_char = extract_main_character(sets, player_id, character_lookup)
        normalized_main = main_char.lower() if isinstance(main_char, str) else None
        matches_filter = normalized_target is None or normalized_main == normalized_target

        if matches_filter or include_without_character:
            rows.append({
                "Player": player.get("gamerTag"),
                "Region": (player.get("user") or {}).get("location", {}).get("state") if player.get("user") else None,
                "Main": main_char,
                "WinRate": win_rate,
                "SetsAnalyzed": len(sets),
                "MatchesFilter": matches_filter,
                "Tournament": (record.get("tournament") or {}).get("name"),
                "Event": (record.get("event") or {}).get("name"),
            })
    return pd.DataFrame(rows)


__all__ = [
    "compute_win_rate",
    "extract_main_character",
    "generate_character_report",
]
