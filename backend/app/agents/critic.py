import json
import re

from app.agents.base import AgentEvent, EventCallback, noop_emit
from app.config import MODEL_CRITIC
from app.qwen_client import chat_with_usage

_SYSTEM = (
    "You are a senior code reviewer acting as a Critic in a multi-agent system. "
    "You receive a coding problem, the plan that was followed, the code that was written, "
    "and a report of which tests failed and why.\n\n"
    "Decide what to do next. Output ONLY valid JSON with this exact structure:\n"
    '{"action": "patch" | "replan" | "give_up", "reasoning": "...", "guidance": "..."}\n\n'
    "Rules:\n"
    "- 'patch': the plan is sound but the implementation has a fixable bug. "
    "Set 'guidance' to a specific hint for the Coder.\n"
    "- 'replan': the plan itself is wrong or the approach won't work. "
    "Set 'guidance' to a different strategy for the Planner.\n"
    "- 'give_up': the problem is unsolvable with the current information, or the failures "
    "suggest a fundamental misunderstanding of the problem that can't be fixed quickly.\n"
    "No prose outside the JSON."
)


def critique(
    plan: dict,
    code: str,
    failure_report: str,
    attempt_count: int,
    replan_count: int,
    emit: EventCallback = noop_emit,
) -> tuple[dict, dict]:
    """
    Returns (decision_dict, usage).
    decision_dict: {action: str, reasoning: str, guidance: str}
    """
    emit(AgentEvent("critic", "start", {
        "attempt": attempt_count,
        "replans_used": replan_count,
    }))

    plan_text = (
        f"Approach: {plan.get('approach', '')}\n"
        f"Edge cases: {', '.join(plan.get('edge_cases', []))}\n"
        f"Complexity target: {plan.get('complexity_target', '')}"
    )

    user_content = (
        f"Plan:\n{plan_text}\n\n"
        f"Code (attempt {attempt_count}):\n```python\n{code}\n```\n\n"
        f"Failure report:\n{failure_report}\n\n"
        f"Replans used so far: {replan_count}"
    )

    content, usage = chat_with_usage(
        model=MODEL_CRITIC,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
    )

    decision = _parse_decision(content)
    emit(AgentEvent("critic", "output", {
        "action": decision["action"],
        "reasoning": decision["reasoning"],
        "guidance": decision["guidance"],
        "raw": content,
    }))
    return decision, usage


def _parse_decision(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        d = json.loads(text)
        if d.get("action") not in ("patch", "replan", "give_up"):
            d["action"] = "patch"  # safe fallback
        return d
    except json.JSONDecodeError:
        return {"action": "patch", "reasoning": "parse error", "guidance": text[:300]}
