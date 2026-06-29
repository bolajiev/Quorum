"""
Loads cached results.json and produces the payload the frontend chart consumes.
Also used by the /api/benchmark endpoint.
"""
import json
import pathlib

RESULTS_PATH = pathlib.Path(__file__).parent / "results.json"


def load_results(path: pathlib.Path | None = None) -> dict | None:
    p = path or RESULTS_PATH
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def chart_payload(results: dict) -> dict:
    """
    Returns the JSON structure the frontend Chart.js scoreboard expects:
    {
      summary: { quorum: {...}, baseline: {...} },
      race: [
        { id, difficulty, quorum: {solved, attempts, tokens, latency}, baseline: {...} }
      ]
    }
    """
    race = []
    for row in results["problems"]:
        race.append({
            "id": row["id"],
            "difficulty": row["difficulty"],
            "quorum": {
                "solved": row["quorum"]["solved"],
                "attempts": row["quorum"]["attempts_used"],
                "tokens": row["quorum"]["total_tokens"],
                "latency": row["quorum"]["wall_clock_seconds"],
                "replans": row["quorum"]["replan_count"],
            },
            "baseline": {
                "solved": row["baseline"]["solved"],
                "attempts": row["baseline"]["attempts_used"],
                "tokens": row["baseline"]["total_tokens"],
                "latency": row["baseline"]["wall_clock_seconds"],
            },
        })

    return {
        "run_at": results["run_at"],
        "summary": results["summary"],
        "race": race,
    }
