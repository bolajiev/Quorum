'use strict';

// ── Config ───────────────────────────────────────────────────────────────────
const WS_BASE  = `ws://${location.host}/ws/solve`;
const API_BASE = `${location.protocol}//${location.host}`;
const MAX_DOTS = 4;

// ── State ────────────────────────────────────────────────────────────────────
const sys = {
  quorum:   { ws: null, dotStates: Array(MAX_DOTS).fill('idle'), entries: [], patches: 0, replans: 0 },
  baseline: { ws: null, dotStates: Array(MAX_DOTS).fill('idle'), entries: [], patches: 0, replans: 0 },
};
let activeTab    = 'quorum';
let benchmarkData = null;
let tokenChart   = null;
let problemsData = [];

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $select        = document.getElementById('problem-select');
const $transcript    = document.getElementById('transcript');
const $statusBar     = document.getElementById('status-bar');
const $btnQ          = document.getElementById('btn-quorum');
const $btnB          = document.getElementById('btn-baseline');
const $btnBoth       = document.getElementById('btn-both');
const $clearBtn      = document.getElementById('clear-btn');
const $customStrip   = document.getElementById('custom-strip');
const $customProblem = document.getElementById('custom-problem');
const $problemBanner = document.getElementById('problem-banner');
const $problemBannerText = document.getElementById('problem-banner-text');

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadProblems();
  loadBenchmark();

  $btnQ   .addEventListener('click', () => runSolve('quorum'));
  $btnB   .addEventListener('click', () => runSolve('baseline'));
  $btnBoth.addEventListener('click', () => { runSolve('quorum'); runSolve('baseline'); });
  $clearBtn.addEventListener('click', clearTranscript);
  $select.addEventListener('change', onProblemChange);

  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => switchTab(t.dataset.system));
  });
});

// ── Problem selection ─────────────────────────────────────────────────────────
function onProblemChange() {
  const id = $select.value;
  const isCustom = id === 'custom';

  $customStrip.style.display = isCustom ? 'block' : 'none';

  if (isCustom) {
    $problemBanner.style.display = 'none';
  } else {
    const prob = problemsData.find(p => p.id === id);
    if (prob) {
      $problemBannerText.textContent = prob.prompt;
      $problemBanner.style.display = 'flex';
    }
  }
}

// ── Problems dropdown ─────────────────────────────────────────────────────────
async function loadProblems() {
  try {
    const customOpt = document.createElement('option');
    customOpt.value = 'custom';
    customOpt.textContent = '✏  Custom Problem';
    $select.appendChild(customOpt);

    const sep = document.createElement('option');
    sep.disabled = true;
    sep.textContent = '──────────────────';
    $select.appendChild(sep);

    problemsData = await fetch(`${API_BASE}/api/problems`).then(r => r.json());
    problemsData.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.id} · ${p.difficulty}`;
      $select.appendChild(opt);
    });

    // Default to first real problem
    if (problemsData.length) {
      $select.value = problemsData[0].id;
      onProblemChange();
    }
  } catch (e) {
    console.error('Failed to load problems', e);
  }
}

// ── Benchmark scoreboard ─────────────────────────────────────────────────────
async function loadBenchmark() {
  try {
    benchmarkData = await fetch(`${API_BASE}/api/benchmark`).then(r => r.json());
    renderScoreboard(benchmarkData);
  } catch (e) {
    document.getElementById('scoreboard-content').innerHTML =
      '<div class="loading">No benchmark data. Run benchmark/runner.py to generate.</div>';
  }
}

function renderScoreboard(data) {
  const { summary, race, run_at } = data;
  const q = summary.quorum, b = summary.baseline;

  const el = document.getElementById('scoreboard-content');
  el.innerHTML = `
    <div class="stats-grid">
      <div class="stat-box">
        <div class="label">Solve Rate</div>
        <div class="stat-row">
          <span class="stat-val quorum">${(q.solve_rate*100).toFixed(0)}%</span>
          <span class="stat-sub">Quorum</span>
        </div>
        <div class="stat-row">
          <span class="stat-val baseline">${(b.solve_rate*100).toFixed(0)}%</span>
          <span class="stat-sub">Baseline</span>
        </div>
      </div>
      <div class="stat-box">
        <div class="label">Avg Attempts</div>
        <div class="stat-row">
          <span class="stat-val quorum">${q.avg_attempts.toFixed(1)}</span>
          <span class="stat-sub">Quorum</span>
        </div>
        <div class="stat-row">
          <span class="stat-val baseline">${b.avg_attempts.toFixed(1)}</span>
          <span class="stat-sub">Baseline</span>
        </div>
      </div>
      <div class="stat-box">
        <div class="label">Avg Tokens</div>
        <div class="stat-row">
          <span class="stat-val quorum">${Math.round(q.avg_tokens_all)}</span>
          <span class="stat-sub">Quorum</span>
        </div>
        <div class="stat-row">
          <span class="stat-val baseline">${Math.round(b.avg_tokens_all)}</span>
          <span class="stat-sub">Baseline</span>
        </div>
      </div>
      <div class="stat-box">
        <div class="label">Avg Latency</div>
        <div class="stat-row">
          <span class="stat-val quorum">${q.avg_latency_seconds.toFixed(1)}s</span>
          <span class="stat-sub">Quorum</span>
        </div>
        <div class="stat-row">
          <span class="stat-val baseline">${b.avg_latency_seconds.toFixed(1)}s</span>
          <span class="stat-sub">Baseline</span>
        </div>
      </div>
    </div>

    <div class="chart-wrap">
      <div class="chart-title">Planning investment — tokens per problem</div>
      <canvas id="token-chart"></canvas>
    </div>

    <table class="prob-table">
      <thead><tr>
        <th>ID</th><th>Diff</th>
        <th style="color:var(--coder)">Q ✓</th>
        <th style="color:var(--coder)">Q att</th>
        <th style="color:var(--planner)">B ✓</th>
        <th style="color:var(--planner)">B att</th>
      </tr></thead>
      <tbody>
        ${race.map(r => `
          <tr>
            <td class="id-col">${r.id}</td>
            <td class="diff-${r.difficulty}">${r.difficulty}</td>
            <td>${r.quorum.solved   ? '<span class="check">✓</span>' : '<span class="cross">✕</span>'}</td>
            <td>${r.quorum.attempts}</td>
            <td>${r.baseline.solved ? '<span class="check">✓</span>' : '<span class="cross">✕</span>'}</td>
            <td>${r.baseline.attempts}</td>
          </tr>`).join('')}
      </tbody>
    </table>
    <div style="font-size:9px;color:var(--muted);font-family:var(--font-mono);text-align:right">
      run at ${run_at}
    </div>
  `;

  if (tokenChart) tokenChart.destroy();
  const ctx = document.getElementById('token-chart').getContext('2d');
  tokenChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: race.map(r => r.id),
      datasets: [
        { label: 'Quorum',   data: race.map(r => r.quorum.tokens),   backgroundColor: 'rgba(79,184,174,.7)',  borderColor: 'rgba(79,184,174,1)',  borderWidth: 1, borderRadius: 2 },
        { label: 'Baseline', data: race.map(r => r.baseline.tokens), backgroundColor: 'rgba(232,163,61,.6)', borderColor: 'rgba(232,163,61,1)', borderWidth: 1, borderRadius: 2 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: true, animation: { duration: 400 },
      plugins: { legend: { labels: { color: '#7A8499', font: { family: 'IBM Plex Mono', size: 10 }, boxWidth: 10 } } },
      scales: {
        x: { ticks: { color: '#7A8499', font: { family: 'IBM Plex Mono', size: 9 } }, grid: { color: 'rgba(42,47,58,.6)' } },
        y: { ticks: { color: '#7A8499', font: { family: 'IBM Plex Mono', size: 9 } }, grid: { color: 'rgba(42,47,58,.6)' } },
      },
    },
  });
}

// ── Solve via WebSocket ───────────────────────────────────────────────────────
function runSolve(system) {
  const problemId = $select.value;
  if (!problemId) return;

  if (problemId === 'custom') {
    const text = $customProblem.value.trim();
    if (!text) {
      $customProblem.focus();
      $customProblem.style.borderColor = 'var(--critic)';
      setTimeout(() => $customProblem.style.borderColor = '', 1500);
      return;
    }
  }

  if (sys[system].ws) { sys[system].ws.close(); sys[system].ws = null; }

  resetRace(system);
  sys[system].entries  = [];
  sys[system].patches  = 0;
  sys[system].replans  = 0;
  updateNegotiations(system);
  if (activeTab === system) renderTranscript();

  setStatus('running', `Running ${system} on ${problemId}…`);

  const ws = new WebSocket(WS_BASE);
  sys[system].ws = ws;
  setButtons(true);

  ws.addEventListener('open', () => {
    const payload = { system, problem_id: problemId };
    if (problemId === 'custom') payload.problem_text = $customProblem.value.trim();
    ws.send(JSON.stringify(payload));
  });

  ws.addEventListener('message', ({ data }) => {
    const msg = JSON.parse(data);
    if (msg.type === 'result') handleResult(system, msg);
    else handleEvent(system, msg);
  });

  ws.addEventListener('close', () => {
    sys[system].ws = null;
    if (!sys.quorum.ws && !sys.baseline.ws) setButtons(false);
  });

  ws.addEventListener('error', () => {
    appendEntry(system, 'orchestrator', 'error', { text: 'Connection error' });
    sys[system].ws = null;
    setButtons(false);
    setStatus('failed', 'WebSocket error');
  });
}

// ── Event handling ────────────────────────────────────────────────────────────
function handleEvent(system, msg) {
  const { agent, type, data } = msg;

  const phaseMap = { planner: 'PLANNING', coder: 'CODING', verifier: 'VERIFYING', critic: 'CRITIQUING' };
  if (phaseMap[agent]) setPhase(system, phaseMap[agent]);

  if (agent === 'coder' && type === 'start') {
    const idx = (data.attempt || 1) - 1;
    setDot(system, idx, 'active');
    setDotLabel(system, idx, String(data.attempt));
  }
  if (agent === 'verifier' && type === 'output') {
    const activeDot = sys[system].dotStates.indexOf('active');
    if (activeDot >= 0) setDot(system, activeDot, data.passed ? 'pass' : 'fail');
  }

  // ── Critic: show negotiation card ─────────────────────────────────────────
  if (agent === 'critic' && type === 'output') {
    const action = (data.action || '').toLowerCase();
    if (action === 'patch')   { sys[system].patches++; updateNegotiations(system); }
    if (action === 'replan')  { sys[system].replans++; updateNegotiations(system); }
    appendEntry(system, 'critic', 'negotiation', { action, reasoning: data.reasoning, guidance: data.guidance });
    return;
  }

  // ── Normal entries ────────────────────────────────────────────────────────
  let text = '', extra = null;

  if (agent === 'planner' && type === 'output') {
    text = `Approach: ${data.approach || ''}`;
    if (data.edge_cases?.length) text += `\nEdge cases: ${data.edge_cases.join(', ')}`;
    if (data.complexity_target)  text += `\nComplexity: ${data.complexity_target}`;
  } else if (agent === 'coder' && type === 'start') {
    text = `Attempt ${data.attempt}…`;
  } else if (agent === 'coder' && type === 'output') {
    const lines = (data.code || '').split('\n').slice(0, 8).join('\n');
    const truncated = (data.code || '').split('\n').length > 8;
    extra = { code: lines + (truncated ? '\n…' : '') };
  } else if (agent === 'coder' && type === 'error') {
    text = `⚠ ${data.reason || 'No code block returned'}`;
  } else if (agent === 'verifier' && type === 'output') {
    if (data.passed && data.note) text = `✓ ${data.note}`;
    else if (data.passed)         text = '✓ All tests passed';
    else {
      const fr = parseFR(data.failure_report);
      text = `✕ ${data.num_failures} test(s) failed — ${fr}`;
    }
  } else if (agent === 'orchestrator' && type === 'tests_generated') {
    text = `Planner generated ${data.count} test case(s) — code will be verified against them`;
  } else if (agent === 'orchestrator' && type === 'done') {
    text = data.status === 'solved'
      ? `✓ SOLVED in ${data.attempts} attempt(s)`
      : `✕ UNSOLVED — ${data.reason || ''}`;
    setPhase(system, '');
  } else {
    return;
  }

  if (text || extra) appendEntry(system, agent, type, { text, extra });
}

function handleResult(system, msg) {
  const verdict = msg.solved ? 'pass' : 'fail';
  setVerdict(system, verdict, msg.solved ? 'SOLVED' : 'FAILED');

  const allDone = !sys.quorum.ws && !sys.baseline.ws;
  if (allDone) {
    setStatus(msg.solved ? 'solved' : 'failed',
      `${msg.solved ? 'Solved' : 'Failed'} · ${msg.total_tokens} tok · ${msg.wall_clock_seconds?.toFixed(1)}s`);
  }
}

// ── Transcript rendering ──────────────────────────────────────────────────────
function appendEntry(system, agent, type, payload) {
  sys[system].entries.push({ agent, type, payload, ts: Date.now() });
  if (activeTab === system) renderTranscript();
}

function renderTranscript() {
  const entries = sys[activeTab].entries;
  if (!entries.length) {
    $transcript.innerHTML = '<div class="empty-state">Select a problem and press Run to start.</div>';
    return;
  }

  $transcript.innerHTML = entries.map(e => {
    if (e.type === 'negotiation') return renderNegotiationCard(e);
    return renderNormalEntry(e);
  }).join('<hr class="tx-divider">');

  $transcript.scrollTop = $transcript.scrollHeight;
}

function renderNegotiationCard(e) {
  const { action, reasoning, guidance } = e.payload;
  const actionClass = action === 'give_up' ? 'give_up' : action;
  const actionLabel = action === 'give_up' ? 'GIVE UP' : action.toUpperCase();
  return `
    <div class="tx-negotiation">
      <div class="tx-negotiation-header">
        <span class="tx-negotiation-label">CRITIC DECISION</span>
        <span class="tx-action-badge ${actionClass}">${actionLabel}</span>
      </div>
      ${reasoning ? `<div class="tx-negotiation-reasoning">${escHtml(reasoning)}</div>` : ''}
      ${guidance  ? `<div class="tx-negotiation-guidance">→ ${escHtml(guidance)}</div>` : ''}
    </div>`;
}

function renderNormalEntry(e) {
  const { text, extra } = e.payload;
  let bodyHtml = '';
  if (text) {
    const cls = text.startsWith('✓') ? 'pass' : text.startsWith('✕') ? 'fail' : '';
    bodyHtml += `<div class="tx-body ${cls}">${escHtml(text)}</div>`;
  }
  if (extra?.code) {
    bodyHtml += `<pre class="tx-code">${escHtml(extra.code)}</pre>`;
  }
  return `<div class="tx-entry">
    <div class="tx-header">
      <span class="tx-chip" data-agent="${e.agent}">${e.agent.toUpperCase()}</span>
    </div>
    ${bodyHtml}
  </div>`;
}

function switchTab(system) {
  activeTab = system;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.system === system));
  renderTranscript();
}

function clearTranscript() {
  sys.quorum.entries   = []; sys.quorum.patches   = 0; sys.quorum.replans   = 0;
  sys.baseline.entries = []; sys.baseline.patches = 0; sys.baseline.replans = 0;
  updateNegotiations('quorum');
  renderTranscript();
}

// ── Race helpers ──────────────────────────────────────────────────────────────
function resetRace(system) {
  sys[system].dotStates = Array(MAX_DOTS).fill('idle');
  document.querySelectorAll(`#dots-${system} .dot`).forEach((d, i) => {
    d.removeAttribute('data-state');
    d.setAttribute('data-n', String(i + 1));
  });
  setPhase(system, '');
  const v = document.getElementById(`verdict-${system}`);
  if (v) { v.className = 'lane-verdict'; v.textContent = ''; }
}

function setDot(system, idx, state) {
  if (idx < 0 || idx >= MAX_DOTS) return;
  sys[system].dotStates[idx] = state;
  const dot = document.querySelector(`#dots-${system} .dot[data-idx="${idx}"]`);
  if (dot) dot.setAttribute('data-state', state);
}

function setDotLabel(system, idx, label) {
  const dot = document.querySelector(`#dots-${system} .dot[data-idx="${idx}"]`);
  if (dot) dot.setAttribute('data-n', label);
}

function setPhase(system, phase) {
  const el = document.getElementById(`phase-${system}`);
  if (el) el.textContent = phase;
}

function setVerdict(system, cls, text) {
  const el = document.getElementById(`verdict-${system}`);
  if (el) { el.className = `lane-verdict show ${cls}`; el.textContent = text; }
}

function updateNegotiations(system) {
  const el = document.getElementById(`neg-${system}`);
  if (!el) return;
  const { patches, replans } = sys[system];
  el.innerHTML = '';
  if (patches > 0) el.insertAdjacentHTML('beforeend', `<span class="neg-badge patch">${patches} patch${patches>1?'es':''}</span>`);
  if (replans > 0) el.insertAdjacentHTML('beforeend', `<span class="neg-badge replan">${replans} replan${replans>1?'s':''}</span>`);
}

// ── UI helpers ────────────────────────────────────────────────────────────────
function setButtons(running) {
  [$btnQ, $btnB, $btnBoth].forEach(b => b.disabled = running);
}

function setStatus(cls, text) {
  $statusBar.className = `status-bar ${cls}`;
  $statusBar.textContent = text;
}

function parseFR(raw) {
  if (!raw) return '';
  try { const o = JSON.parse(raw); return o.summary || o.suggestion || ''; }
  catch { return String(raw).slice(0, 80); }
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/\n/g, '<br>');
}
