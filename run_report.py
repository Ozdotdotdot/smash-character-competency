#!/usr/bin/env python3
"""CLI helper to print the latest player metrics for a given state."""

import argparse
import os

import pandas as pd

import smash_analysis as analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate start.gg player metrics for a region.")
    parser.add_argument("state", help="Two-letter state code (e.g. GA)")
    parser.add_argument(
        "--character",
        default="Marth",
        help="Character name to emphasise (default: Marth)",
    )
    parser.add_argument(
        "--videogame-id",
        type=int,
        default=1386,
        help="Videogame id (1386 = Super Smash Bros. Ultimate)",
    )
    parser.add_argument(
        "--months-back",
        type=int,
        default=6,
        help="Rolling window in months (default: 6)",
    )
    args = parser.parse_args()

    if not os.getenv("STARTGG_API_TOKEN"):
        print("STARTGG_API_TOKEN environment variable not set. Export it before running.")
        return

    try:
        df = analysis.generate_player_metrics(
            state=args.state,
            months_back=args.months_back,
            videogame_id=args.videogame_id,
            target_character=args.character,
        )
        if df.empty:
            print("No players found in the requested window.")
            return

        display_cols = [
            "gamer_tag",
            "state",
            "events_played",
        "sets_played",
        "win_rate",
        "weighted_win_rate",
        "avg_seed_delta",
        "opponent_strength",
        "character_usage_rate",
    ]
        available_cols = [c for c in display_cols if c in df.columns]
        print(df[available_cols].to_string(index=False))
    except Exception as exc:
        print("Error running report:", exc)


if __name__ == "__main__":
    main()
