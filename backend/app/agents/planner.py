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


def plan(
    problem_prompt: str,
    critic_feedback: str = "",
    emit: EventCallback = noop_emit,
) -> tuple[dict, dict]:
    """Returns (plan_dict, usage)."""
    emit(AgentEvent("planner", "start", {"has_feedback": bool(critic_feedback)}))

    user_content = problem_prompt
    if critic_feedback:
        user_content += f"\n\nPrevious approach failed. Critic feedback:\n{critic_feedback}"

    content, usage = chat_with_usage(
        model=MODEL_PLANNER,
        messages=[
            {"role": "system", "content": _SYSTEM},
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
