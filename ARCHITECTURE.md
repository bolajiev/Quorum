# Quorum — Architecture

## System Diagram

![Quorum Architecture](docs/architecture-diagram.svg)

---

## Orchestration Loop

Quorum decomposes every competitive-programming problem across four specialised roles. Each role has a strict JSON output contract enforced in code — a loosely-typed agent boundary reads as unfinished.

| Agent | Model | Contract |
|---|---|---|
| **Planner** | qwen-turbo | `{approach, edge_cases, test_ideas, complexity_target}` |
| **Coder** | qwen-max | Code only — single fenced `python` block, no prose |
| **Verifier** | deterministic + qwen-turbo (summariser) | `{passed, failures, failure_report}` |
| **Critic** | qwen-plus | `{action: patch\|replan\|give_up, reasoning, guidance}` |

### State Machine

```
Problem → Planner → Coder → Verifier ──pass──→ SOLVED
                       ↑         │
                    patch        │ fail
                       │         ↓
                       └──── CRITIC ──replan──→ Planner
                                  │
                               give_up
                                  ↓
                               UNSOLVED
```

**Hard caps (enforced in code, not prompts):**
- Max **4 Coder attempts** per problem
- Max **2 replans** per problem
- Both caps checked before the Critic runs — it cannot override them

The Critic decision is the disagreement-resolution mechanism Track 3 explicitly requires. Every decision is logged verbatim to the event stream.

---

## Single-Agent Baseline

`baseline/single_agent.py` — one `qwen-plus` call gets the problem directly. No Planner, no Critic. It still gets the **same** sandbox, the **same** 4-attempt cap, and the **same** self-debug loop (feeds its own traceback back). Same total budget, no role split.

This is what makes the benchmark comparison meaningful instead of a strawman.

---

## Sandbox Isolation

Generated code **never** executes in the orchestrator's process.

**Development (local):** `sandbox/local_subprocess.py` — subprocess with `resource` ulimits (CPU, memory), no inherited env, 8 s hard timeout.

**Production (Alibaba Cloud):** `sandbox/fc_client.py` → `sandbox_function/handler.py` on Function Compute. Each invocation is a fresh, isolated, auto-torn-down container. This is also the "proof of Alibaba Cloud deployment" file — invoking it is an Alibaba Cloud API call.

The sandbox router in `sandbox/__init__.py` switches automatically: if `FC_ENDPOINT` is set, it uses Function Compute; otherwise it falls back to the local subprocess.

---

## Deployment

```
Browser  ──WebSocket / REST──→  FastAPI (ECS, ap-southeast-1)
                                     │
                          ┌──────────┴──────────┐
                          ↓                     ↓
                   Qwen Cloud API        Function Compute
                   (LLM inference)       (code sandbox)
```

- **ECS**: single burstable instance, uvicorn + systemd. Deploy: `bash infra/deploy_ecs.sh`
- **Function Compute**: `sandbox_function/` deployed via Serverless Devs. Deploy: `bash infra/deploy_fc.sh`
- **Frontend**: static HTML/CSS/JS served by FastAPI's `StaticFiles` mount — no build step

---

## Benchmark Harness

`benchmark/runner.py` runs both systems on all 15 problems (HumanEval-style, MIT licensed) under identical conditions and caches results to `benchmark/results.json`. The frontend reads this file for the scoreboard.

Metrics collected per problem per system: `solved`, `attempts_used`, `replan_count`, `total_tokens`, `wall_clock_seconds`, `sandbox_runs`.

To re-run: `cd backend && PYTHONPATH=. python3 -m app.benchmark.runner`
