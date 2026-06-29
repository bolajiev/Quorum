from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class AgentEvent:
    agent: str   # planner | coder | verifier | critic | orchestrator
    type: str    # start | output | error | done
    data: Any = None


EventCallback = Callable[[AgentEvent], None]


def noop_emit(event: AgentEvent) -> None:
    pass
