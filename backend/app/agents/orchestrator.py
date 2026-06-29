import time
from dataclasses import dataclass, field

from app import config
from app.agents import coder, critic, planner, verifier
from app.agents.base import AgentEvent, EventCallback, noop_emit


@dataclass
class OrchestrationState:
    problem_id: str
    coder_attempts: int = 0
    replan_count: int = 0
    plan: dict = field(default_factory=dict)
    last_code: str | None = None
    last_failure_report: str | None = None
    status: str = "planning"


@dataclass
class QuorumResult:
    solved: bool
    attempts_used: int
    replan_count: int
    total_tokens: int
    wall_clock_seconds: float
    sandbox_runs: int
    final_code: str | None = None
    failure_reason: str | None = None
    token_log: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)


def solve(problem: dict, emit: EventCallback = noop_emit) -> QuorumResult:
    """
    Full state machine: Planner → Coder → Verifier → Critic → (patch | replan | give_up)
    Hard caps enforced in code (rule §0.3): MAX_CODER_ATTEMPTS, MAX_REPLAN_COUNT.
    """
    start = time.monotonic()
    total_tokens = 0
    token_log: list[dict] = []
    sandbox_runs = 0
    events: list[dict] = []

    def _emit(event: AgentEvent) -> None:
        events.append({"agent": event.agent, "type": event.type, "data": event.data})
        emit(event)

    def _track(usage: dict, phase: str) -> None:
        nonlocal total_tokens
        total_tokens += usage["total_tokens"]
        token_log.append({"phase": phase, **usage})

    def _finish(solved: bool, reason: str | None = None) -> QuorumResult:
        _emit(AgentEvent("orchestrator", "done", {
            "status": "solved" if solved else "unsolved",
            "reason": reason,
            "attempts": state.coder_attempts,
            "replans": state.replan_count,
        }))
        return QuorumResult(
            solved=solved,
            attempts_used=state.coder_attempts,
            replan_count=state.replan_count,
            total_tokens=total_tokens,
            wall_clock_seconds=time.monotonic() - start,
            sandbox_runs=sandbox_runs,
            final_code=state.last_code,
            failure_reason=reason,
            token_log=token_log,
            events=events,
        )

    state = OrchestrationState(problem_id=problem["id"])
    _emit(AgentEvent("orchestrator", "start", {"problem_id": problem["id"]}))

    # For custom problems without tests, ask the Planner to generate them
    is_custom = not problem.get("tests")

    # ── Initial plan ──────────────────────────────────────────────────────────
    plan_dict, usage = planner.plan(
        problem["prompt"], emit=_emit, generate_tests=is_custom
    )
    _track(usage, "plan_0")
    state.plan = plan_dict
    state.status = "coding"

    # Use planner-generated tests if the problem has none
    tests = problem.get("tests") or []
    if is_custom and plan_dict.get("sample_tests"):
        tests = plan_dict["sample_tests"]
        _emit(AgentEvent("orchestrator", "tests_generated", {
            "count": len(tests),
            "source": "planner",
        }))

    # ── Main loop ─────────────────────────────────────────────────────────────
    while state.coder_attempts < config.MAX_CODER_ATTEMPTS:
        state.coder_attempts += 1

        # — Coder —
        code_str, _, usage = coder.code(
            plan=state.plan,
            problem_prompt=problem["prompt"],
            failure_report=state.last_failure_report or "",
            attempt=state.coder_attempts,
            emit=_emit,
        )
        _track(usage, f"code_{state.coder_attempts}")

        if code_str is None:
            state.last_failure_report = (
                "Your response had no ```python ... ``` block. "
                "Output ONLY a fenced Python solution."
            )
            continue

        state.last_code = code_str

        # — Verifier —
        sandbox_runs += 1
        state.status = "verifying"
        result, v_usage = verifier.verify(code_str, tests, emit=_emit)
        if v_usage:
            _track(v_usage, f"verify_summarize_{state.coder_attempts}")

        if result["passed"]:
            state.status = "solved"
            return _finish(solved=True)

        state.last_failure_report = result.get("failure_report", "Tests failed.")
        state.status = "coding"

        # — Cap check before Critic —
        # If we've exhausted all coder attempts, no point consulting Critic.
        if state.coder_attempts >= config.MAX_CODER_ATTEMPTS:
            break

        # — Critic —
        state.status = "critiquing"
        decision, usage = critic.critique(
            plan=state.plan,
            code=code_str,
            failure_report=state.last_failure_report,
            attempt_count=state.coder_attempts,
            replan_count=state.replan_count,
            emit=_emit,
        )
        _track(usage, f"critic_{state.coder_attempts}")

        action = decision["action"]

        if action == "give_up":
            return _finish(solved=False, reason=f"Critic gave up: {decision['reasoning']}")

        if action == "replan":
            if state.replan_count >= config.MAX_REPLAN_COUNT:
                # Hard cap — cannot replan further regardless of Critic's wish
                return _finish(solved=False, reason="Replan cap reached")
            state.replan_count += 1
            feedback = decision["reasoning"] + "\nNew direction: " + decision["guidance"]
            plan_dict, usage = planner.plan(
                problem["prompt"], feedback, emit=_emit, generate_tests=is_custom
            )
            _track(usage, f"replan_{state.replan_count}")
            state.plan = plan_dict
            if is_custom and plan_dict.get("sample_tests"):
                tests = plan_dict["sample_tests"]
            state.last_failure_report = None  # fresh plan, drop old failures

        else:  # patch
            # Append Critic's guidance to the failure report so Coder sees it
            state.last_failure_report = (
                state.last_failure_report
                + f"\nCritic guidance: {decision['guidance']}"
            )

        state.status = "coding"

    return _finish(solved=False, reason="Coder attempt cap reached")
