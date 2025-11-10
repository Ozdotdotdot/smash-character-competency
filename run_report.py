#!/usr/bin/env python3
"""CLI helper to print the latest player metrics for a given state."""

import argparse
import os
from datetime import datetime, timezone

import pandas as pd

from smashcc import analysis


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
    parser.add_argument(
        "--output",
        help="Optional path to write the full metrics as a CSV instead of printing the table.",
    )
    parser.add_argument(
        "--assume-target-main",
        action="store_true",
        help="If set, treat the target character as a player's main when no character data is reported.",
    )
    parser.add_argument(
        "--filter-state",
        action="append",
        help="Only include players whose state matches one of the provided values. Use multiple times for multiple states.",
    )
    parser.add_argument(
        "--min-entrants",
        type=int,
        help="Keep players whose average event entrant count is at least this value.",
    )
    parser.add_argument(
        "--max-entrants",
        type=int,
        help="Keep players whose average event entrant count is at most this value.",
    )
    parser.add_argument(
        "--start-after",
        help="Keep players whose latest event started on or after this date (YYYY-MM-DD).",
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
            assume_target_main=args.assume_target_main,
        )
        if df.empty:
            print("No players found in the requested window.")
            return

        if args.filter_state:
            allowed = {s.upper() for s in args.filter_state}
            state_series = df["home_state"].fillna("").str.upper()
            mask = state_series.isin(allowed)
            df = df[mask]

        if args.min_entrants is not None and "avg_event_entrants" in df.columns:
            df = df[df["avg_event_entrants"].fillna(0) >= args.min_entrants]

        if args.max_entrants is not None and "avg_event_entrants" in df.columns:
            df = df[df["avg_event_entrants"].fillna(0) <= args.max_entrants]

        if args.start_after:
            try:
                cutoff = datetime.fromisoformat(args.start_after).replace(tzinfo=timezone.utc)
            except ValueError:
                print(f"Invalid --start-after date '{args.start_after}'. Expected YYYY-MM-DD.")
                return
            cutoff_ts = int(cutoff.timestamp())
            df = df[df["latest_event_start"].fillna(0) >= cutoff_ts]

        if df.empty:
            print("No players matched the supplied filters.")
            return

        if args.output:
            df.to_csv(args.output, index=False)
            print(f"Wrote {len(df)} rows to {args.output}")
            return

        display_cols = [
            "gamer_tag",
            "state",
            "home_state",
            "home_state_inferred",
            "home_country",
            "events_played",
            "sets_played",
            "avg_event_entrants",
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
