import pathlib

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.benchmark import report as bench_report

app = FastAPI(title="Quorum")

FRONTEND = pathlib.Path(__file__).parent.parent.parent / "frontend"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/benchmark")
def get_benchmark():
    results = bench_report.load_results()
    if results is None:
        return JSONResponse({"error": "No benchmark results yet. Run benchmark/runner.py first."}, status_code=404)
    return bench_report.chart_payload(results)


@app.get("/api/problems")
def get_problems():
    import json
    p = pathlib.Path(__file__).parent / "benchmark" / "problems" / "problems.json"
    with open(p) as f:
        return json.load(f)


@app.websocket("/ws/solve")
async def ws_solve(websocket: WebSocket):
    """
    Live solve endpoint.
    Client sends: {"system": "quorum"|"baseline", "problem_id": "HE-1"}
    Server streams agent events as JSON-encoded text frames.
    """
    import asyncio
    import json

    await websocket.accept()
    loop = asyncio.get_running_loop()
    disconnected = False

    async def safe_send(payload: dict) -> None:
        nonlocal disconnected
        if disconnected:
            return
        try:
            await websocket.send_text(json.dumps(payload, default=str))
        except Exception:
            disconnected = True

    def on_event(e) -> None:
        if not disconnected:
            asyncio.run_coroutine_threadsafe(
                safe_send({"agent": e.agent, "type": e.type, "data": e.data}),
                loop,
            )

    try:
        data = await websocket.receive_json()
        system = data.get("system", "quorum")
        problem_id = data.get("problem_id", "HE-1")

        p = pathlib.Path(__file__).parent / "benchmark" / "problems" / "problems.json"
        with open(p) as f:
            problems = {prob["id"]: prob for prob in json.load(f)}

        if problem_id not in problems:
            await safe_send({"type": "error", "message": f"Unknown problem: {problem_id}"})
            return

        problem = problems[problem_id]

        if system == "quorum":
            from app.agents.orchestrator import solve
            result = await loop.run_in_executor(None, lambda: solve(problem, emit=on_event))
        else:
            from app.baseline.single_agent import solve
            result = await loop.run_in_executor(None, lambda: solve(problem))

        await safe_send({
            "type": "result",
            "solved": result.solved,
            "attempts_used": result.attempts_used,
            "total_tokens": result.total_tokens,
            "wall_clock_seconds": round(result.wall_clock_seconds, 2),
        })

    except WebSocketDisconnect:
        pass


# Static frontend — mounted last so API routes take priority
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
