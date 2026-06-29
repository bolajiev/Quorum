from app.agents.base import AgentEvent, EventCallback, noop_emit
from app.config import MODEL_PLANNER
from app.qwen_client import chat_with_usage
from app.sandbox.local_subprocess import run_tests

_SUMMARIZE_SYSTEM = (
    "You are a debugging assistant. Given test failures, output ONLY compact JSON:\n"
    '{"summary": "one-line root cause", '
    '"failing_tests": [{"id": "...", "expected": "...", "actual": "..."}], '
    '"suggestion": "brief fix hint"}\n'
    "IMPORTANT: If actual output is empty, the program produced no output — "
    "the most likely cause is a function that is defined but never called, or a missing print() call. "
    "Say so explicitly in the summary.\n"
    "No prose outside the JSON."
)


def verify(
    code: str,
    tests: list[dict],
    emit: EventCallback = noop_emit,
) -> tuple[dict, dict | None]:
    """
    Runs code against tests in the sandbox.
    Returns (result_dict, usage_or_None).
    result_dict always has {passed, failures}.
    On failure also has {failure_report} — a compact LLM summary.
    usage_or_None is the token usage from summarization (None on pass).
    """
    emit(AgentEvent("verifier", "start", {"num_tests": len(tests)}))

    if not tests:
        emit(AgentEvent("verifier", "output", {
            "passed": True,
            "note": "No test cases provided — code accepted. Review output manually.",
        }))
        return {"passed": True, "failures": []}, None

    result = run_tests(code, tests)

    if result["passed"]:
        emit(AgentEvent("verifier", "output", {"passed": True}))
        return result, None

    failure_report, usage = _summarize_failures(result["failures"])
    result["failure_report"] = failure_report

    emit(AgentEvent("verifier", "output", {
        "passed": False,
        "num_failures": len(result["failures"]),
        "failure_report": failure_report,
    }))

    return result, usage


def _summarize_failures(failures: list[dict]) -> tuple[str, dict]:
    raw = "\n".join(
        f"Test {f['test_id']}: expected={f['expected']!r}, got={f['actual']!r}\n"
        f"{f.get('traceback', '')[:400]}"
        for f in failures
    )
    content, usage = chat_with_usage(
        model=MODEL_PLANNER,
        messages=[
            {"role": "system", "content": _SUMMARIZE_SYSTEM},
            {"role": "user", "content": raw},
        ],
        temperature=0,
    )
    return content.strip(), usage
