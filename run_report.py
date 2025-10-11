~#!/usr/bin/env python3
"""Small CLI to run generate_character_report with a real API token.

Set STARTGG_API_TOKEN in your environment before running. This script will
print a simple table of results.
"""
import argparse
import os
import pandas as pd
import smash_analysis as analysis


def main():
    parser = argparse.ArgumentParser(description="Run a character report using start.gg API")
    parser.add_argument("state", help="Two-letter state code (e.g. GA)")
    parser.add_argument("character", help="Character name to filter on (e.g. Marth)")
    parser.add_argument("--videogame-id", type=int, default=1386, help="Videogame id (1386=Ultimate)")
    args = parser.parse_args()

    token = os.getenv("STARTGG_API_TOKEN")
    if not token:
        print("STARTGG_API_TOKEN environment variable not set. Set it to run live queries.")
        return

    try:
        df = analysis.generate_character_report(
            args.state,
            args.character,
            videogame_id=args.videogame_id,
        )
        if df.empty:
            print("No players found matching criteria.")
        else:
            print(df.to_string(index=False))
    except Exception as e:
        print("Error running report:", e)


if __name__ == "__main__":
    main()
