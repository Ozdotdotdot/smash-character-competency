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
from typing import List, Dict, Any, Optional


_character_cache: Dict[int, Dict[str, str]] = {}


def get_character_map(videogame_id: int) -> Dict[str, str]:
    """Return a mapping from character id to name for a given game."""
    if videogame_id in _character_cache:
        return _character_cache[videogame_id]

    query = """
    query($id: ID!) {
      videogame(id: $id) {
        characters {
          id
          name
        }
      }
    }
    """
    data = _post_graphql(query, {"id": videogame_id})
    characters = data["videogame"].get("characters") or []
    if isinstance(characters, dict) and "nodes" in characters:
        characters = characters["nodes"]
    lookup = {str(c["id"]): c["name"] for c in characters if c.get("id") and c.get("name")}
    _character_cache[videogame_id] = lookup
    return lookup


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


def get_events_for_tournament(tournament_id: int) -> List[dict]:
    """Fetch event payloads for a tournament."""
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
    events = data.get("tournament", {}).get("events") or []
    return events


def get_event_ids_for_tournament(tournament_id: int) -> List[int]:
    """Convenience wrapper returning only the event ids for a tournament."""
    return [e.get("id") for e in get_events_for_tournament(tournament_id) if e.get("id")]


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

def fetch_state_tournaments(
    state: str,
    videogame_id: int = 1386,
    per_page_tournaments: int = 3,
    per_page_entrants: int = 10,
) -> List[Dict[str, Any]]:
    """Return tournaments with nested events and entrant payloads for a state."""
    tournaments = get_tournaments_by_state(
        state,
        videogame_id=videogame_id,
        per_page=per_page_tournaments,
    )
    results: List[Dict[str, Any]] = []
    for tournament in tournaments:
        events = []
        for event in get_events_for_tournament(tournament.get("id")):
            event_id = event.get("id")
            entrants = get_event_entrants(event_id, per_page=per_page_entrants) if event_id else []
            events.append({
                "event": event,
                "entrants": entrants,
            })
        results.append({
            "tournament": tournament,
            "events": events,
        })
    return results


def fetch_state_player_records(
    state: str,
    videogame_id: int = 1386,
    per_page_tournaments: int = 3,
    per_page_entrants: int = 10,
    per_page_sets: int = 10,
) -> List[Dict[str, Any]]:
    """Return a list of player-centric records with raw set payloads."""
    tournaments = fetch_state_tournaments(
        state,
        videogame_id=videogame_id,
        per_page_tournaments=per_page_tournaments,
        per_page_entrants=per_page_entrants,
    )
    records: List[Dict[str, Any]] = []
    for tournament_entry in tournaments:
        tournament = tournament_entry.get("tournament") or {}
        for event_entry in tournament_entry.get("events", []):
            event = event_entry.get("event") or {}
            for entrant in event_entry.get("entrants", []) or []:
                for participant in (entrant.get("participants") or []):
                    player = participant.get("player")
                    if not player or not player.get("id"):
                        continue
                    sets = get_player_sets(player["id"], per_page=per_page_sets)
                    records.append({
                        "tournament": tournament,
                        "event": event,
                        "entrant": entrant,
                        "player": player,
                        "sets": sets,
                    })
    return records


__all__ = [
    "API_URL",
    "get_character_map",
    "get_tournaments_by_state",
    "get_events_for_tournament",
    "get_event_ids_for_tournament",
    "get_event_entrants",
    "get_player_sets",
    "fetch_state_tournaments",
    "fetch_state_player_records",
]
