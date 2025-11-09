"""
datastore.py
------------

Persistence helpers for storing start.gg payloads in a local SQLite database.
The goal is to retain historical tournament/event data so notebook + CLI usage
can avoid re-downloading the same tournaments after the initial fetch.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional


class SQLiteStore:
    """Small helper that persists tournaments + event payloads locally."""

    def __init__(
        self,
        path: Optional[Path] = None,
        discovery_ttl_days: int = 7,
    ) -> None:
        self.path = path or Path(".cache") / "startgg" / "smash.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.discovery_ttl = timedelta(days=discovery_ttl_days)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    # --------------------------------------------------------------------- #
    # Schema & lifecycle
    # --------------------------------------------------------------------- #

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self.conn.close()

    def _ensure_schema(self) -> None:
        """Create tables if they do not already exist."""
        self.conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS tournaments (
                id INTEGER PRIMARY KEY,
                slug TEXT,
                name TEXT,
                city TEXT,
                state TEXT,
                start_at INTEGER,
                end_at INTEGER,
                num_attendees INTEGER,
                videogame_id INTEGER,
                last_synced INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tournaments_state_game_start
              ON tournaments(state, videogame_id, start_at DESC);

            CREATE TABLE IF NOT EXISTS discoveries (
                state TEXT NOT NULL,
                videogame_id INTEGER NOT NULL,
                last_synced INTEGER NOT NULL,
                PRIMARY KEY (state, videogame_id)
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                tournament_id INTEGER NOT NULL,
                slug TEXT,
                name TEXT,
                start_at INTEGER,
                num_entrants INTEGER,
                videogame_id INTEGER,
                payload TEXT NOT NULL,
                last_synced INTEGER NOT NULL,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_events_tournament
              ON events(tournament_id);

            CREATE TABLE IF NOT EXISTS event_payloads (
                event_id INTEGER PRIMARY KEY,
                seeds_json TEXT NOT NULL,
                standings_json TEXT NOT NULL,
                sets_json TEXT NOT NULL,
                last_synced INTEGER NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            );
            """
        )
        self.conn.commit()

    # --------------------------------------------------------------------- #
    # Discovery metadata
    # --------------------------------------------------------------------- #

    def discovery_is_stale(self, state: str, videogame_id: int) -> bool:
        """Return True when the tournament listing needs a refresh."""
        row = self.conn.execute(
            "SELECT last_synced FROM discoveries WHERE state = ? AND videogame_id = ?",
            (state.upper(), int(videogame_id)),
        ).fetchone()
        if row is None:
            return True
        last_synced = datetime.fromtimestamp(row["last_synced"], tz=timezone.utc)
        return (datetime.now(timezone.utc) - last_synced) >= self.discovery_ttl

    def record_discovery(self, state: str, videogame_id: int) -> None:
        """Persist the timestamp for the most recent tournament discovery run."""
        now_ts = int(datetime.now(timezone.utc).timestamp())
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO discoveries(state, videogame_id, last_synced)
                VALUES (?, ?, ?)
                ON CONFLICT(state, videogame_id) DO UPDATE SET last_synced = excluded.last_synced
                """,
                (state.upper(), int(videogame_id), now_ts),
            )

    # --------------------------------------------------------------------- #
    # Tournaments
    # --------------------------------------------------------------------- #

    def upsert_tournaments(self, tournaments: Iterable[Dict], videogame_id: int) -> None:
        """Insert or update tournament rows after hitting the API."""
        now_ts = int(datetime.now(timezone.utc).timestamp())
        with self.conn:
            for tourney in tournaments:
                self.conn.execute(
                    """
                    INSERT INTO tournaments(
                        id, slug, name, city, state, start_at, end_at,
                        num_attendees, videogame_id, last_synced
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        slug = excluded.slug,
                        name = excluded.name,
                        city = excluded.city,
                        state = excluded.state,
                        start_at = excluded.start_at,
                        end_at = excluded.end_at,
                        num_attendees = excluded.num_attendees,
                        videogame_id = excluded.videogame_id,
                        last_synced = excluded.last_synced
                    """,
                    (
                        int(tourney.get("id")),
                        tourney.get("slug"),
                        tourney.get("name"),
                        tourney.get("city"),
                        (tourney.get("addrState") or tourney.get("state", "")),
                        tourney.get("startAt"),
                        tourney.get("endAt"),
                        tourney.get("numAttendees"),
                        int(videogame_id),
                        now_ts,
                    ),
                )

    def load_tournaments(
        self,
        state: str,
        videogame_id: int,
        cutoff_ts: int,
    ) -> List[Dict]:
        """Return tournaments in the requested window from SQLite."""
        rows = self.conn.execute(
            """
            SELECT *
              FROM tournaments
             WHERE state = ?
               AND videogame_id = ?
               AND start_at >= ?
             ORDER BY start_at DESC
            """,
            (state.upper(), int(videogame_id), cutoff_ts),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "slug": row["slug"],
                "name": row["name"],
                "city": row["city"],
                "addrState": row["state"],
                "startAt": row["start_at"],
                "endAt": row["end_at"],
                "numAttendees": row["num_attendees"],
            }
            for row in rows
        ]

    # --------------------------------------------------------------------- #
    # Events
    # --------------------------------------------------------------------- #

    def save_events(self, tournament_id: int, events: Iterable[Dict]) -> None:
        """Persist event metadata for a tournament."""
        now_ts = int(datetime.now(timezone.utc).timestamp())
        with self.conn:
            for event in events:
                payload = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
                videogame = event.get("videogame") or {}
                videogame_id = videogame.get("id")
                self.conn.execute(
                    """
                    INSERT INTO events(
                        id, tournament_id, slug, name, start_at, num_entrants,
                        videogame_id, payload, last_synced
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        slug = excluded.slug,
                        name = excluded.name,
                        start_at = excluded.start_at,
                        num_entrants = excluded.num_entrants,
                        videogame_id = excluded.videogame_id,
                        payload = excluded.payload,
                        last_synced = excluded.last_synced
                    """,
                    (
                        int(event.get("id")),
                        int(tournament_id),
                        event.get("slug"),
                        event.get("name"),
                        event.get("startAt"),
                        event.get("numEntrants"),
                        int(videogame_id) if videogame_id is not None else None,
                        payload,
                        now_ts,
                    ),
                )

    def load_events(self, tournament_id: int) -> List[Dict]:
        """Load persisted events for a tournament."""
        rows = self.conn.execute(
            """
            SELECT payload
              FROM events
             WHERE tournament_id = ?
             ORDER BY start_at DESC
            """,
            (int(tournament_id),),
        ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    # --------------------------------------------------------------------- #
    # Event bundles (seeds/standings/sets)
    # --------------------------------------------------------------------- #

    def save_event_bundle(
        self,
        event_id: int,
        seeds: Iterable[Dict],
        standings: Iterable[Dict],
        sets: Iterable[Dict],
    ) -> None:
        """Persist the per-event bundle once downloaded."""
        now_ts = int(datetime.now(timezone.utc).timestamp())
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO event_payloads(
                    event_id, seeds_json, standings_json, sets_json, last_synced
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    seeds_json = excluded.seeds_json,
                    standings_json = excluded.standings_json,
                    sets_json = excluded.sets_json,
                    last_synced = excluded.last_synced
                """,
                (
                    int(event_id),
                    json.dumps(list(seeds), separators=(",", ":"), ensure_ascii=False),
                    json.dumps(list(standings), separators=(",", ":"), ensure_ascii=False),
                    json.dumps(list(sets), separators=(",", ":"), ensure_ascii=False),
                    now_ts,
                ),
            )

    def load_event_bundle(self, event_id: int) -> Optional[Dict]:
        """Return a cached bundle for the event, if available."""
        row = self.conn.execute(
            """
            SELECT seeds_json, standings_json, sets_json
              FROM event_payloads
             WHERE event_id = ?
            """,
            (int(event_id),),
        ).fetchone()
        if row is None:
            return None
        return {
            "seeds": json.loads(row["seeds_json"]),
            "standings": json.loads(row["standings_json"]),
            "sets": json.loads(row["sets_json"]),
        }
