"""FastAPI entrypoint exposing the Smash Character Competency analytics."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Query

from smashcc.analysis import generate_player_metrics

app = FastAPI(
    title="Smash Character Competency API",
    description="Lightweight API exposing player metrics derived from start.gg data.",
    version="0.1.0",
)


@app.get("/health")
def health() -> Dict[str, bool]:
    """Simple liveness endpoint."""
    return {"ok": True}


@app.get("/search")
def search(
    state: str = Query(..., description="Two-letter region/state code."),
    character: str = Query("Marth", description="Character to emphasise in the metrics."),
    months_back: int = Query(
        6,
        ge=1,
        le=24,
        description="How many months of tournaments to include.",
    ),
    videogame_id: int = Query(
        1386,
        description="start.gg videogame identifier (Ultimate = 1386, Melee = 1).",
    ),
    assume_target_main: bool = Query(
        False,
        description="Treat the target character as a main when set data is missing.",
    ),
    limit: int = Query(
        25,
        ge=1,
        le=200,
        description="Maximum number of player records to return.",
    ),
) -> Dict[str, Any]:
    """
    Run the analytics pipeline and return a table of player metrics suitable for display.
    """
    token = os.getenv("STARTGG_API_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="Missing STARTGG_API_TOKEN")

    try:
        df = generate_player_metrics(
            state=state,
            months_back=months_back,
            videogame_id=videogame_id,
            target_character=character,
            assume_target_main=assume_target_main,
        )
    except Exception as exc:  # pragma: no cover - protective circuit
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    records: List[Dict[str, Any]] = df.head(limit).to_dict(orient="records")
    return {
        "state": state,
        "character": character,
        "count": len(records),
        "results": records,
    }
