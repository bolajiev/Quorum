import json
import re

from app.agents.base import AgentEvent, EventCallback, noop_emit
from app.config import MODEL_PLANNER
from app.qwen_client import chat_with_usage

_SYSTEM = (
    "You are a competitive programming strategist. "
    "Given a problem, output ONLY valid JSON with this exact structure:\n"
    '{"approach": "...", "edge_cases": ["..."], "test_ideas": ["..."], "complexity_target": "..."}\n'
    "No prose, no markdown fences — raw JSON only."
)

_SYSTEM_WITH_TESTS = (
    "You are a competitive programming strategist. "
    "Given a problem, output ONLY valid JSON with this exact structure:\n"
    '{"approach": "...", "edge_cases": ["..."], "test_ideas": ["..."], "complexity_target": "...", '
    '"sample_tests": [{"id": "t1", "input": "...", "expected_output": "..."}, ...]}\n'
    "Rules for sample_tests:\n"
    "- Generate 4-6 test cases that cover normal cases, edge cases, and tricky inputs.\n"
    "- 'input' is EXACTLY what the program reads from stdin (use \\n for newlines between lines).\n"
    "- 'expected_output' is EXACTLY what the program should print to stdout (no trailing newline).\n"
    "- Make test cases that would catch greedy/naive bugs — include at least one trap case.\n"
    "No prose, no markdown fences — raw JSON only."
)


def plan(
    problem_prompt: str,
    critic_feedback: str = "",
    emit: EventCallback = noop_emit,
    generate_tests: bool = False,
) -> tuple[dict, dict]:
    """Returns (plan_dict, usage)."""
    emit(AgentEvent("planner", "start", {"has_feedback": bool(critic_feedback)}))

    user_content = problem_prompt
    if critic_feedback:
        user_content += f"\n\nPrevious approach failed. Critic feedback:\n{critic_feedback}"

    system = _SYSTEM_WITH_TESTS if generate_tests else _SYSTEM

    content, usage = chat_with_usage(
        model=MODEL_PLANNER,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
    )

    plan_dict = _parse_plan(content)
    emit(AgentEvent("planner", "output", plan_dict))
    return plan_dict, usage


def _parse_plan(text: str) -> dict:
    # Strip markdown fences if the model adds them anyway
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "approach": text,
            "edge_cases": [],
            "test_ideas": [],
            "complexity_target": "unknown",
        }
