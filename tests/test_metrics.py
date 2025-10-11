import math

from metrics import compute_player_metrics
from smash_data import PlayerEventResult, SetRecord


def _base_event():
    return {
        "id": 10,
        "name": "Test Event",
        "slug": "tournament/test/event/test-event",
        "startAt": 1_700_000_000,
        "numEntrants": 32,
    }


def _base_tournament():
    return {
        "id": 1,
        "name": "Test Tournament",
        "slug": "tournament/test",
        "city": "Atlanta",
        "addrState": "GA",
        "startAt": 1_700_000_000,
    }


def _participant(player_id: int, gamer_tag: str, state: str = "GA"):
    return {
        "id": 999,
        "gamerTag": gamer_tag,
        "player": {
            "id": player_id,
            "gamerTag": gamer_tag,
            "user": {
                "location": {
                    "city": "Atlanta",
                    "state": state,
                    "country": "USA",
                }
            },
        },
    }


def test_compute_player_metrics_single_player():
    event = _base_event()
    tournament = _base_tournament()
    participant = _participant(1000, "Alice")

    set_win = SetRecord(
        set_id="1",
        won=True,
        opponent_entrant_id="E2",
        opponent_player_ids=[2000],
        opponent_gamer_tags=["Bob"],
        opponent_seed=2,
        opponent_placement=2,
        round_text="Winners Quarterfinals",
        completed_at=1_700_000_100,
        characters=["Marth"],
    )
    set_loss = SetRecord(
        set_id="2",
        won=False,
        opponent_entrant_id="E3",
        opponent_player_ids=[3000],
        opponent_gamer_tags=["Carol"],
        opponent_seed=7,
        opponent_placement=5,
        round_text="Winners Semifinals",
        completed_at=1_700_000_200,
        characters=["Marth"],
    )

    result = PlayerEventResult(
        player_id=1000,
        gamer_tag="Alice",
        entrant_id="E1",
        seed_num=5,
        placement=3,
        participant=participant,
        event=event,
        tournament=tournament,
        sets=[set_win, set_loss],
    )

    df = compute_player_metrics([result], target_character="Marth")
    assert not df.empty

    row = df.iloc[0]
    assert math.isclose(row["win_rate"], 0.5)
    assert math.isclose(row["weighted_win_rate"], row["win_rate"])
    assert math.isclose(row["avg_seed_delta"], 2.0)
    assert row["events_played"] == 1
    assert row["sets_played"] == 2
    assert row["character_sets"] == 2
    assert math.isclose(row["character_win_rate"], 0.5)
    assert math.isclose(row["character_usage_rate"], 1.0)
    assert math.isclose(row["upset_rate"], 1.0)
