# Quorum — 3-Minute Demo Script

**Total runtime: ~3:00**  
Record at 1080p. Keep the terminal closed — show only the browser.

---

## SEGMENT 1 — Problem framing (0:00 – 0:30)

**Show:** Quorum console, scoreboard visible, no solve running yet.

**Say (or title card):**
> "Quorum is a multi-agent system for competitive programming. Instead of one model trying to solve a problem alone, four specialised agents collaborate: a Planner that structures the approach, a Coder that implements it, a Verifier that runs tests in an isolated sandbox, and a Critic that reviews failures and decides whether to patch, replan, or give up. We benchmark it head-to-head against a single-agent baseline — same model family, same retry budget, same sandbox — to measure whether role separation actually helps."

**Camera:** slow scroll down the scoreboard showing 15/15 vs 15/15, lingering on the token comparison chart.

---

## SEGMENT 2 — Live multi-agent dialogue (0:30 – 2:00)

**Setup before recording:**
- Select **HE-13** (palindromic substring length) — this problem has shown retry behaviour in testing and benefits visibly from the Planner's structured output.
- Have the console at full width so the transcript is readable.

**Action:**
1. Click **"Run Both"** — both race lanes activate simultaneously.
2. **Quorum lane:** watch the first dot pulse (Coder attempt 1).
3. **Transcript tab — Quorum:** shows Planner output first (approach, edge cases), then Coder attempt.
4. If Verifier passes on attempt 1: keep going. If it fails, the Critic fires — **pause here** and zoom into the Critic entry showing `action: PATCH` or `action: REPLAN` with its reasoning. This is the key moment.
5. **Baseline lane** resolves in parallel — usually faster but without the structured dialogue.

**To guarantee a visible Critic + replan for the demo:**
- Before recording, run `HE-7` (valid parentheses) in dev — it has triggered multi-attempt behaviour. Alternatively, temporarily increase `MAX_CODER_ATTEMPTS` to 4 and reduce Coder temperature to 0 to make the first attempt more deterministic.

**What to highlight:**
- The role-coloured chips in the transcript (amber Planner → teal Coder → violet Verifier → rust Critic)
- The Critic's JSON decision visible in the transcript: `action: replan | reasoning: ... | guidance: ...`
- The Planner receiving the Critic's feedback and generating a new plan
- Both race lanes finishing, one dot green per system

---

## SEGMENT 3 — Scoreboard reveal (2:00 – 3:00)

**Show:** Switch to Scoreboard tab / scroll down to the benchmark panel.

**Highlight:**
1. **Solve rate**: 15/15 both systems — equal correctness on this problem set.
2. **Token comparison chart** (grouped bars): Quorum uses ~3× the tokens — honest overhead of the planning layer.
3. **The architectural argument**: "On this problem set both systems solve everything in one attempt. The value of the multi-agent structure shows on harder problems and at scale: the Planner prevents the Coder from starting with a wrong approach, and the Critic prevents wasted retries on a fundamentally broken plan. The structured failure reports are also cheaper to feed back into context than raw tracebacks."
4. **Architecture diagram**: briefly show `ARCHITECTURE.md` — the state machine and deployment diagram.

**Closing shot:** the QUORUM console, race lanes both green, transcript showing the full Planner → Coder → Verifier → Solved flow.

---

## Shot checklist

- [ ] Console at full browser width, browser chrome hidden (F11 fullscreen)
- [ ] Font rendering: confirm Space Grotesk loaded (check Network tab)
- [ ] Status bar shows "Solved · N tok · X.Xs" after each run
- [ ] Both race lane dots are green before closing shot
- [ ] Benchmark scoreboard loaded (not "No benchmark data" error)
- [ ] Screen recording at 1920×1080, 30fps minimum
- [ ] Audio: clean voiceover or title cards — no background noise
- [ ] Duration: trim to ≤3:00 before upload

---

## Upload

Upload to YouTube (unlisted is fine) or Vimeo. Paste the URL into the submission form under "Demo Video."
