'use strict';

// ── Config ───────────────────────────────────────────────────────────────────
const WS_BASE  = `ws://${location.host}/ws/solve`;
const API_BASE = `${location.protocol}//${location.host}`;
const MAX_DOTS = 4;

// ── State ────────────────────────────────────────────────────────────────────
const sys = {
  quorum:   { ws: null, dotStates: Array(MAX_DOTS).fill('idle'), entries: [] },
  baseline: { ws: null, dotStates: Array(MAX_DOTS).fill('idle'), entries: [] },
};
let activeTab = 'quorum';
let benchmarkData = null;
let tokenChart = null;

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $select       = document.getElementById('problem-select');
const $transcript   = document.getElementById('transcript');
const $statusBar    = document.getElementById('status-bar');
const $btnQ         = document.getElementById('btn-quorum');
const $btnB         = document.getElementById('btn-baseline');
const $btnBoth      = document.getElementById('btn-both');
const $clearBtn     = document.getElementById('clear-btn');
const $customStrip  = document.getElementById('custom-strip');
const $customProblem= document.getElementById('custom-problem');

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadProblems();
  loadBenchmark();

  $btnQ   .addEventListener('click', () => runSolve('quorum'));
  $btnB   .addEventListener('click', () => runSolve('baseline'));
  $btnBoth.addEventListener('click', () => { runSolve('quorum'); runSolve('baseline'); });
  $clearBtn.addEventListener('click', clearTranscript);
  $select.addEventListener('change', toggleCustomStrip);

  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => switchTab(t.dataset.system));
  });
});

// ── Problems dropdown ─────────────────────────────────────────────────────────
async function loadProblems() {
  try {
    // Custom option first
    const customOpt = document.createElement('option');
    customOpt.value = 'custom';
    customOpt.textContent = '✏ Custom Problem';
    $select.appendChild(customOpt);

    const sep = document.createElement('option');
    sep.disabled = true;
    sep.textContent = '─────────────────';
    $select.appendChild(sep);

    const data = await fetch(`${API_BASE}/api/problems`).then(r => r.json());
    data.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.id} · ${p.difficulty}`;
      $select.appendChild(opt);
    });

    // Default to first real problem
    $select.value = data[0]?.id || 'custom';
    toggleCustomStrip();
  } catch (e) {
    console.error('Failed to load problems', e);
  }
}

function toggleCustomStrip() {
  const isCustom = $select.value === 'custom';
  $customStrip.style.display = isCustom ? 'block' : 'none';
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
      <div class="chart-title">Tokens per problem — Quorum vs Baseline</div>
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

  // Chart.js token comparison
  if (tokenChart) tokenChart.destroy();
  const ctx = document.getElementById('token-chart').getContext('2d');
  tokenChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: race.map(r => r.id),
      datasets: [
        {
          label: 'Quorum',
          data: race.map(r => r.quorum.tokens),
          backgroundColor: 'rgba(79,184,174,.7)',
          borderColor: 'rgba(79,184,174,1)',
          borderWidth: 1,
          borderRadius: 2,
        },
        {
          label: 'Baseline',
          data: race.map(r => r.baseline.tokens),
          backgroundColor: 'rgba(232,163,61,.6)',
          borderColor: 'rgba(232,163,61,1)',
          borderWidth: 1,
          borderRadius: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      animation: { duration: 400 },
      plugins: {
        legend: { labels: { color: '#7A8499', font: { family: 'IBM Plex Mono', size: 10 }, boxWidth: 10 } },
      },
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

  // Close any existing WS for this system
  if (sys[system].ws) { sys[system].ws.close(); sys[system].ws = null; }

  resetRace(system);
  sys[system].entries = [];
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
    if (msg.type === 'result') {
      handleResult(system, msg);
    } else {
      handleEvent(system, msg);
    }
  });

  ws.addEventListener('close', () => {
    sys[system].ws = null;
    if (!sys.quorum.ws && !sys.baseline.ws) setButtons(false);
  });

  ws.addEventListener('error', () => {
    appendEntry(system, 'orchestrator', 'error', 'Connection error');
    sys[system].ws = null;
    setButtons(false);
    setStatus('failed', 'WebSocket error');
  });
}

// ── Event handling ────────────────────────────────────────────────────────────
function handleEvent(system, msg) {
  const { agent, type, data } = msg;

  // Update race phase
  const phase = { planner: 'PLANNING', coder: 'CODING', verifier: 'VERIFYING', critic: 'CRITIQUING', orchestrator: '' };
  if (phase[agent]) setPhase(system, phase[agent]);

  // Update race dots on coder events
  if (agent === 'coder' && type === 'start') {
    const idx = (data.attempt || 1) - 1;
    setDot(system, idx, 'active');
    setDotLabel(system, idx, String(data.attempt));
  }
  if (agent === 'verifier' && type === 'output') {
    // Mark the current active dot
    const activeDot = sys[system].dotStates.indexOf('active');
    if (activeDot >= 0) setDot(system, activeDot, data.passed ? 'pass' : 'fail');
  }

  // Build transcript entry
  let text = '', extra = null;
  if (agent === 'planner' && type === 'output') {
    text = `Approach: ${data.approach || ''}`;
    if (data.edge_cases?.length) text += `\nEdge cases: ${data.edge_cases.join(', ')}`;
  } else if (agent === 'coder' && type === 'start') {
    text = `Attempt ${data.attempt}…`;
  } else if (agent === 'coder' && type === 'output') {
    const lines = (data.code || '').split('\n').slice(0, 8).join('\n');
    const truncated = (data.code || '').split('\n').length > 8;
    extra = { code: lines + (truncated ? '\n…' : '') };
    text = '';
  } else if (agent === 'coder' && type === 'error') {
    text = `⚠ ${data.reason || 'No code block returned'}`;
  } else if (agent === 'verifier' && type === 'output') {
    if (data.passed && data.note) {
      text = `✓ ${data.note}`;
    } else if (data.passed) {
      text = '✓ All tests passed';
    } else {
      const fr = parseFR(data.failure_report);
      text = `✕ ${data.num_failures} test(s) failed — ${fr}`;
    }
  } else if (agent === 'critic' && type === 'output') {
    text = `action: ${(data.action || '').toUpperCase()}  ·  ${(data.reasoning || '').slice(0, 100)}`;
    if (data.guidance) text += `\nGuidance: ${data.guidance.slice(0, 100)}`;
  } else if (agent === 'orchestrator' && type === 'done') {
    text = data.status === 'solved'
      ? `✓ SOLVED in ${data.attempts} attempt(s)`
      : `✕ UNSOLVED — ${data.reason || ''}`;
    setPhase(system, '');
  } else {
    return; // skip start/other noisy events
  }

  if (text || extra) appendEntry(system, agent, type, text, extra);
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
function appendEntry(system, agent, type, text, extra) {
  sys[system].entries.push({ agent, type, text, extra, ts: Date.now() });
  if (activeTab === system) renderTranscript();
}

function renderTranscript() {
  const entries = sys[activeTab].entries;
  if (!entries.length) {
    $transcript.innerHTML = '<div class="empty-state">Select a problem and press Run to start.</div>';
    return;
  }
  $transcript.innerHTML = entries.map(e => {
    const label = e.agent.toUpperCase().padEnd(10);
    let bodyHtml = '';
    if (e.text) {
      const cls = e.text.startsWith('✓') ? 'pass' : e.text.startsWith('✕') ? 'fail' : '';
      bodyHtml += `<div class="tx-body ${cls}">${escHtml(e.text)}</div>`;
    }
    if (e.extra?.code) {
      bodyHtml += `<pre class="tx-code">${escHtml(e.extra.code)}</pre>`;
    }
    return `<div class="tx-entry">
      <div class="tx-header">
        <span class="tx-chip" data-agent="${e.agent}">${e.agent.toUpperCase()}</span>
        <span class="tx-label">${label}</span>
      </div>
      ${bodyHtml}
    </div>`;
  }).join('<hr class="tx-divider">');

  $transcript.scrollTop = $transcript.scrollHeight;
}

function switchTab(system) {
  activeTab = system;
  document.querySelectorAll('.tab').forEach(t => {
    t.classList.toggle('active', t.dataset.system === system);
  });
  renderTranscript();
}

function clearTranscript() {
  sys.quorum.entries = [];
  sys.baseline.entries = [];
  renderTranscript();
}

// ── Race lane helpers ─────────────────────────────────────────────────────────
function resetRace(system) {
  sys[system].dotStates = Array(MAX_DOTS).fill('idle');
  document.querySelectorAll(`#dots-${system} .dot`).forEach((d, i) => {
    d.removeAttribute('data-state');
    d.setAttribute('data-n', String(i + 1));
  });
  setPhase(system, '');
  const v = document.getElementById(`verdict-${system}`);
  v.className = 'lane-verdict';
  v.textContent = '';
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
  el.className = `lane-verdict show ${cls}`;
  el.textContent = text;
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
  try {
    const obj = JSON.parse(raw);
    return obj.summary || obj.suggestion || '';
  } catch { return String(raw).slice(0, 80); }
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '<br>');
}
