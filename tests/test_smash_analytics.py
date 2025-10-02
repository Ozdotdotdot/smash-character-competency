import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import smash_analysis as analysis
import smash_analytics as sa


def fake_post_graphql(query, variables=None):
    """A small side-effect mock for _post_graphql used by the tests.

    It looks at the variables to decide which (minimal) response to return and
    mirrors the bits of the start.gg responses that the code under test expects.
    """
    variables = variables or {}
    if "videogame" in query and "characters" in query:
        return {
            "videogame": {
                "characters": [
                    {"id": 1, "name": "Marth"},
                    {"id": 2, "name": "Fox"},
                ]
            }
        }
    # tournaments by state
    if variables.get("state"):
        return {"tournaments": {"nodes": [{"id": 1, "name": "TestT", "city": "TestCity", "addrState": variables["state"], "startAt": 123}]}}
    # events for a tournament (called with variable 'id')
    if variables.get("id") and not variables.get("playerId"):
        return {"tournament": {"events": [{"id": 10, "name": "Main Event"}]}}
    # entrants for an event
    if variables.get("eventId"):
        return {
            "event": {
                "entrants": {
                    "nodes": [
                        {
                            "id": 100,
                            "name": "Entrant One",
                            "participants": [
                                {
                                    "player": {
                                        "id": 1000,
                                        "gamerTag": "Alice",
                                        "user": {"location": {"city": "Atlanta", "state": "GA", "country": "US"}},
                                    }
                                }
                            ],
                        }
                    ]
                }
            }
        }
    # player sets
    if variables.get("playerId"):
        pid = variables.get("playerId")
        if pid == 1000:
            # Two sets: one win, one loss; both played Marth
            return {
                "player": {
                    "sets": {
                        "nodes": [
                            {
                                "id": 1,
                                "displayScore": "2-0",
                                "winnerId": 1000,
                                "slots": [
                                    {
                                        "entrant": {
                                            "id": 100,
                                            "participants": [
                                                {"player": {"id": 1000, "gamerTag": "Alice"}}
                                            ],
                                        }
                                    },
                                    {
                                        "entrant": {
                                            "id": 200,
                                            "participants": [
                                                {"player": {"id": 2000, "gamerTag": "Bob"}}
                                            ],
                                        }
                                    },
                                ],
                                "games": [
                                    {
                                        "id": 11,
                                        "selections": [
                                            {
                                                "selectionType": "Character",
                                                "selectionValue": None,
                                                "entrant": {"id": 100, "participants": [{"player": {"id": 1000}}]},
                                                "character": {"id": 1, "name": "Marth"},
                                            }
                                        ],
                                    }
                                ],
                            },
                            {
                                "id": 2,
                                "displayScore": "1-2",
                                "winnerId": 2000,
                                "slots": [
                                    {
                                        "entrant": {
                                            "id": 100,
                                            "participants": [
                                                {"player": {"id": 1000, "gamerTag": "Alice"}}
                                            ],
                                        }
                                    },
                                    {
                                        "entrant": {
                                            "id": 200,
                                            "participants": [
                                                {"player": {"id": 2000, "gamerTag": "Bob"}}
                                            ],
                                        }
                                    },
                                ],
                                "games": [
                                    {
                                        "id": 12,
                                        "selections": [
                                            {
                                                "selectionType": "Character",
                                                "selectionValue": None,
                                                "entrant": {"id": 100, "participants": [{"player": {"id": 1000}}]},
                                                "character": {"id": 1, "name": "Marth"},
                                            }
                                        ],
                                    }
                                ],
                            },
                        ]
                    }
                }
            }
        # other players: return empty sets
        return {"player": {"sets": {"nodes": []}}}
    return {}


def test_generate_character_report(monkeypatch):
    # Patch the internal _post_graphql function to avoid live HTTP calls.
    monkeypatch.setattr(sa, "_post_graphql", fake_post_graphql)
    sa._character_cache.clear()

    df = analysis.generate_character_report("GA", "Marth", videogame_id=1386)

    # We expect at least one row for Alice
    assert not df.empty
    assert "Alice" in df["Player"].values

    row = df[df["Player"] == "Alice"].iloc[0]
    assert row["Main"] == "Marth"
    assert row["SetsAnalyzed"] == 2
    assert abs(row["WinRate"] - 0.5) < 1e-8
