"""
Single-agent baseline: one model, same sandbox, same 4-attempt cap.
No role split — the model sees the problem and debugs itself.
"""
import re
import time
from dataclasses import dataclass, field

from app import config
from app.qwen_client import chat_with_usage
from app.sandbox.local_subprocess import run_tests


@dataclass
class BaselineResult:
    solved: bool
    attempts_used: int
    total_tokens: int
    wall_clock_seconds: float
    sandbox_runs: int
    final_code: str | None = None
    failure_reason: str | None = None
    token_log: list[dict] = field(default_factory=list)


_SYSTEM = (
    "You are an expert competitive programmer. "
    "When given a problem, respond with ONLY a Python solution wrapped in a single ```python ... ``` block. "
    "No explanation, no prose — code only."
)

_DEBUG_SYSTEM = (
    "You are an expert competitive programmer debugging your own solution. "
    "Given the failing tests, output ONLY a corrected Python solution in a single ```python ... ``` block."
)


def _extract_code(text: str) -> str | None:
    match = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: bare code block
    match = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else None


def _format_failures(failures: list[dict]) -> str:
    lines = []
    for f in failures:
        lines.append(f"Test {f['test_id']}: expected={f['expected']!r}, got={f['actual']!r}")
        if f.get("traceback"):
            lines.append(f"  Traceback: {f['traceback'][:300]}")
    return "\n".join(lines)


def solve(problem: dict) -> BaselineResult:
    """
    problem: {id, prompt, tests: [{id, input, expected_output}]}
    """
    start = time.monotonic()
    total_tokens = 0
    token_log = []
    sandbox_runs = 0
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": problem["prompt"]},
    ]

    last_code = None
    for attempt in range(1, config.MAX_CODER_ATTEMPTS + 1):
        content, usage = chat_with_usage(
            model=config.MODEL_BASELINE,
            messages=messages,
            temperature=0.2,
        )
        total_tokens += usage["total_tokens"]
        token_log.append({"attempt": attempt, **usage})

        code = _extract_code(content)
        if code is None:
            # Model returned no code block — treat as a failed attempt
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": "Your response contained no code block. Reply with ONLY a ```python ... ``` block.",
            })
            continue

        last_code = code
        sandbox_runs += 1
        result = run_tests(code, problem["tests"])

        if result["passed"]:
            elapsed = time.monotonic() - start
            return BaselineResult(
                solved=True,
                attempts_used=attempt,
                total_tokens=total_tokens,
                wall_clock_seconds=elapsed,
                sandbox_runs=sandbox_runs,
                final_code=code,
                token_log=token_log,
            )

        # Feed failures back for self-debug
        failure_text = _format_failures(result["failures"])
        messages.append({"role": "assistant", "content": content})
        messages.append({
            "role": "user",
            "content": (
                f"Your solution failed {len(result['failures'])} test(s):\n{failure_text}\n\n"
                "Fix the solution. Reply with ONLY a corrected ```python ... ``` block."
            ),
        })

    elapsed = time.monotonic() - start
    return BaselineResult(
        solved=False,
        attempts_used=config.MAX_CODER_ATTEMPTS,
        total_tokens=total_tokens,
        wall_clock_seconds=elapsed,
        sandbox_runs=sandbox_runs,
        final_code=last_code,
        failure_reason="Exhausted attempt cap",
        token_log=token_log,
    )
