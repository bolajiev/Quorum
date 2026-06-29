"""
Benchmark harness: runs Quorum and Baseline on the same problem set
under the same budget and sandbox. Saves results to results.json.
"""
import json
import pathlib
import sys
import time
from dataclasses import asdict

from app.agents.orchestrator import solve as quorum_solve
from app.agents.base import AgentEvent
from app.baseline.single_agent import solve as baseline_solve

PROBLEMS_PATH = pathlib.Path(__file__).parent / "problems" / "problems.json"
RESULTS_PATH = pathlib.Path(__file__).parent / "results.json"


def _load_problems(ids: list[str] | None = None) -> list[dict]:
    with open(PROBLEMS_PATH) as f:
        problems = json.load(f)
    if ids:
        problems = [p for p in problems if p["id"] in ids]
    return problems


def run_benchmark(
    problem_ids: list[str] | None = None,
    save_path: pathlib.Path | None = None,
    verbose: bool = True,
) -> dict:
    problems = _load_problems(problem_ids)
    save_path = save_path or RESULTS_PATH
    rows = []

    def _log(msg: str) -> None:
        if verbose:
            print(msg, flush=True)

    for i, p in enumerate(problems, 1):
        _log(f"\n[{i}/{len(problems)}] {p['id']} ({p['difficulty']})")

        # ── Quorum ────────────────────────────────────────────────────────────
        _log("  Quorum  ...", )
        q_events: list[dict] = []

        def _capture(e: AgentEvent) -> None:
            q_events.append({"agent": e.agent, "type": e.type, "data": e.data})

        q = quorum_solve(p, emit=_capture)
        q_status = "SOLVED" if q.solved else "FAILED"
        _log(f"  Quorum  {q_status}  att={q.attempts_used}  tok={q.total_tokens}  replans={q.replan_count}  {q.wall_clock_seconds:.1f}s")

        # ── Baseline ──────────────────────────────────────────────────────────
        _log("  Baseline...", )
        b = baseline_solve(p)
        b_status = "SOLVED" if b.solved else "FAILED"
        _log(f"  Baseline {b_status}  att={b.attempts_used}  tok={b.total_tokens}  {b.wall_clock_seconds:.1f}s")

        rows.append({
            "id": p["id"],
            "difficulty": p["difficulty"],
            "prompt": p["prompt"],
            "quorum": {
                "solved": q.solved,
                "attempts_used": q.attempts_used,
                "replan_count": q.replan_count,
                "total_tokens": q.total_tokens,
                "wall_clock_seconds": round(q.wall_clock_seconds, 2),
                "sandbox_runs": q.sandbox_runs,
                "failure_reason": q.failure_reason,
                "events": q_events,
            },
            "baseline": {
                "solved": b.solved,
                "attempts_used": b.attempts_used,
                "total_tokens": b.total_tokens,
                "wall_clock_seconds": round(b.wall_clock_seconds, 2),
                "sandbox_runs": b.sandbox_runs,
                "failure_reason": b.failure_reason,
            },
        })

    results = {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "num_problems": len(rows),
        "problems": rows,
        "summary": _summarize(rows),
    }

    with open(save_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    _log(f"\nSaved → {save_path}")

    return results


def _summarize(rows: list[dict]) -> dict:
    def _stats(key: str) -> dict:
        solved = [r for r in rows if r[key]["solved"]]
        all_rows = rows
        return {
            "solve_rate": round(len(solved) / len(all_rows), 3) if all_rows else 0,
            "solved": len(solved),
            "total": len(all_rows),
            "avg_attempts": round(
                sum(r[key]["attempts_used"] for r in all_rows) / len(all_rows), 2
            ) if all_rows else 0,
            "avg_tokens_solved": round(
                sum(r[key]["total_tokens"] for r in solved) / len(solved), 0
            ) if solved else 0,
            "avg_tokens_all": round(
                sum(r[key]["total_tokens"] for r in all_rows) / len(all_rows), 0
            ) if all_rows else 0,
            "avg_latency_seconds": round(
                sum(r[key]["wall_clock_seconds"] for r in all_rows) / len(all_rows), 2
            ) if all_rows else 0,
            "total_tokens": sum(r[key]["total_tokens"] for r in all_rows),
        }

    return {"quorum": _stats("quorum"), "baseline": _stats("baseline")}


def summary_text(results: dict) -> str:
    s = results["summary"]
    q, b = s["quorum"], s["baseline"]
    lines = [
        f"\n{'='*50}",
        f"  Benchmark Results — {results['run_at']}",
        f"{'='*50}",
        f"  {'Metric':<28} {'Quorum':>10} {'Baseline':>10}",
        f"  {'-'*48}",
        f"  {'Solve rate':<28} {q['solve_rate']*100:>9.1f}% {b['solve_rate']*100:>9.1f}%",
        f"  {'Solved / Total':<28} {q['solved']:>4}/{q['total']:<5} {b['solved']:>4}/{b['total']:<5}",
        f"  {'Avg attempts':<28} {q['avg_attempts']:>10.2f} {b['avg_attempts']:>10.2f}",
        f"  {'Avg tokens (solved)':<28} {q['avg_tokens_solved']:>10.0f} {b['avg_tokens_solved']:>10.0f}",
        f"  {'Avg latency (s)':<28} {q['avg_latency_seconds']:>10.2f} {b['avg_latency_seconds']:>10.2f}",
        f"  {'Total tokens':<28} {q['total_tokens']:>10} {b['total_tokens']:>10}",
        f"{'='*50}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    ids = sys.argv[1:] or None
    results = run_benchmark(ids, verbose=True)
    print(summary_text(results))
