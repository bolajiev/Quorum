import re

from app.agents.base import AgentEvent, EventCallback, noop_emit
from app.config import MODEL_CODER
from app.qwen_client import chat_with_usage

_SYSTEM = (
    "You are an expert competitive programmer. "
    "Output ONLY a complete, runnable Python program in a single ```python ... ``` block.\n"
    "Requirements:\n"
    "- Read ALL input from stdin using input() or sys.stdin.\n"
    "- Print the answer to stdout using print().\n"
    "- If you define helper functions, you MUST call them and print the result.\n"
    "- Do NOT include example usage, test cases, or any print statements beyond the answer.\n"
    "No prose, no explanation — code only."
)


def code(
    plan: dict,
    problem_prompt: str,
    failure_report: str = "",
    attempt: int = 1,
    emit: EventCallback = noop_emit,
) -> tuple[str | None, str, dict]:
    """
    Returns (code_or_None, raw_content, usage).
    code_or_None is None when the model returned no fenced code block.
    """
    emit(AgentEvent("coder", "start", {"attempt": attempt}))

    plan_text = (
        f"Approach: {plan.get('approach', '')}\n"
        f"Edge cases: {', '.join(plan.get('edge_cases', []))}\n"
        f"Complexity target: {plan.get('complexity_target', '')}"
    )

    if failure_report:
        user_content = (
            f"Problem:\n{problem_prompt}\n\n"
            f"Plan:\n{plan_text}\n\n"
            f"Your previous attempt failed:\n{failure_report}\n\n"
            "Fix the solution. Output ONLY a corrected ```python ... ``` block."
        )
    else:
        user_content = (
            f"Problem:\n{problem_prompt}\n\n"
            f"Plan:\n{plan_text}\n\n"
            "Implement this. Output ONLY a ```python ... ``` block."
        )

    content, usage = chat_with_usage(
        model=MODEL_CODER,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
    )

    extracted = _extract_code(content)
    if extracted:
        emit(AgentEvent("coder", "output", {"code": extracted, "attempt": attempt}))
    else:
        emit(AgentEvent("coder", "error", {"reason": "no_code_block", "raw": content[:300]}))

    return extracted, content, usage


def _extract_code(text: str) -> str | None:
    match = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else None
