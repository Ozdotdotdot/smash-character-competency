# smash-character-competency

This repo contains `smash_analytics.py`, a small helper for querying the start.gg GraphQL API and computing simple player metrics.

Quick start

- Install dependencies (use a virtualenv):

```bash
pip install -r requirements.txt
```

- Run unit tests (they use a mocked API and do not require a token):

```bash
pytest -q
```

- To run a live query against start.gg, set your API token and run the CLI:

```bash
export STARTGG_API_TOKEN="<your_token>"
python run_report.py GA Marth
```

Notes

- The tests mock out `_post_graphql` so you can iterate on analytics logic without making network calls.
- `run_report.py` is a tiny helper to run live reports once you have a token. Be careful: start.gg enforces rate limits and may require pagination for larger data.
