"""
smash_analytics.py
-------------------

Helper functions for pulling Smash Bros tournament data
from the start.gg GraphQL API and computing performance
metrics for players. The goal is to help identify "above-average"
representatives of a character within a region.

This is a skeleton you can extend. Replace placeholders
with your API token and adjust weights/logic as needed.
"""

import os
import requests
import pandas as pd
from typing import List, Dict, Any, Optional


# =====================
# GraphQL Helper
# =====================
API_URL = "https://api.start.gg/gql/alpha"


def _post_graphql(query: str, variables: dict = None) -> dict:
    """
    Perform a GraphQL query against the start.gg API.
    Requires STARTGG_API_TOKEN in your environment.
    """
    token = os.getenv("STARTGG_API_TOKEN")
    if not token:
        raise RuntimeError("Set STARTGG_API_TOKEN as an environment variable.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.post(API_URL, json={"query": query, "variables": variables or {}}, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")
    return data["data"]


# =====================
# Queries
# =====================

def get_tournaments_by_state(state: str, videogame_id: int = 1386, per_page: int = 10) -> List[dict]:
    """
    Fetch tournaments in a given state (2-letter code).
    videogame_id 1386 = Smash Ultimate, 1 = Melee.
    """
    query = """
    query($perPage: Int, $videogameId: ID, $state: String!) {
      tournaments(query: {
        perPage: $perPage
        filter: {
          addrState: $state
          videogameIds: [$videogameId]
        }
      }) {
        nodes {
          id
          name
          city
          addrState
          startAt
        }
      }
    }
    """
    return _post_graphql(query, {"perPage": per_page, "videogameId": videogame_id, "state": state})["tournaments"]["nodes"]


def get_event_ids_for_tournament(tournament_id: int) -> List[int]:
    """Fetch event IDs for a tournament."""
    query = """
    query($id: ID!) {
      tournament(id: $id) {
        events {
          id
          name
        }
      }
    }
    """
    data = _post_graphql(query, {"id": tournament_id})
    return [e["id"] for e in data["tournament"]["events"]]


def get_event_entrants(event_id: int, per_page: int = 25) -> List[dict]:
    """Get entrants for an event, including player info."""
    query = """
    query($eventId: ID!, $perPage: Int) {
      event(id: $eventId) {
        entrants(query: {perPage: $perPage}) {
          nodes {
            id
            name
            participants {
              player {
                id
                gamerTag
                user {
                  location {
                    city
                    state
                    country
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    return _post_graphql(query, {"eventId": event_id, "perPage": per_page})["event"]["entrants"]["nodes"]


def get_player_sets(player_id: int, per_page: int = 10) -> List[dict]:
    """Fetch recent sets for a player, including games and character picks."""
    query = """
    query($playerId: ID!, $perPage: Int) {
      player(id: $playerId) {
        sets(perPage: $perPage) {
          nodes {
            id
            displayScore
            winnerId
            slots {
              entrant {
                id
                participants {
                  player {
                    id
                    gamerTag
                  }
                }
              }
              standing {
                stats {
                  score {
                    value
                  }
                }
              }
            }
            games {
              id
              selections {
                selectionType
                selectionValue
                entrant {
                  id
                }
                character {
                  id
                  name
                }
              }
            }
          }
        }
      }
    }
    """
    return _post_graphql(query, {"playerId": player_id, "perPage": per_page})["player"]["sets"]["nodes"]


# =====================
# Analytics Helpers
# =====================

def compute_win_rate(sets: List[dict], player_id: int) -> float:
    """Compute win rate from a list of sets."""
    if not sets:
        return 0.0
    wins = sum(1 for s in sets if s.get("winnerId") == player_id)
    return wins / len(sets)


def extract_main_character(sets: List[dict], player_id: int) -> Optional[str]:
    """Find the most commonly played character by this player across games."""
    char_counts = {}
    for s in sets:
        for g in s.get("games", []) or []:
            for sel in g.get("selections", []) or []:
                if sel["entrant"] and any(p["player"]["id"] == player_id for p in sel["entrant"].get("participants", [])):
                    char = sel["character"]["name"] if sel["character"] else None
                    if char:
                        char_counts[char] = char_counts.get(char, 0) + 1
    if not char_counts:
        return None
    return max(char_counts, key=char_counts.get)


def generate_character_report(state: str, character: str, videogame_id: int = 1386) -> pd.DataFrame:
    """
    Generate a DataFrame of players in a given state who main a given character.
    Includes gamerTag, win rate, and # of sets analyzed.
    """
    tournaments = get_tournaments_by_state(state, videogame_id=videogame_id, per_page=3)
    rows = []
    for t in tournaments:
        event_ids = get_event_ids_for_tournament(t["id"])
        for e_id in event_ids:
            entrants = get_event_entrants(e_id, per_page=10)
            for entrant in entrants:
                for part in entrant["participants"]:
                    p = part["player"]
                    if not p:
                        continue
                    sets = get_player_sets(p["id"], per_page=10)
                    win_rate = compute_win_rate(sets, p["id"])
                    main_char = extract_main_character(sets, p["id"])
                    if main_char == character:
                        rows.append({
                            "Player": p["gamerTag"],
                            "Region": p["user"]["location"]["state"] if p["user"] and p["user"]["location"] else None,
                            "Main": main_char,
                            "WinRate": win_rate,
                            "SetsAnalyzed": len(sets),
                        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    # Example usage (will only work with a valid API token!)
    try:
        df = generate_character_report("GA", "Marth")
        print(df)
    except Exception as e:
        print("Error:", e)
