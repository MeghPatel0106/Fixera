// ============================================================
// Fixera Dashboard — Frontend Logic
// ============================================================

const PREDICT_URL = '/predict';

// ---- State ----
const history = [];
const stats = { total: 0, high: 0, medium: 0, low: 0 };
const categoryCount = { Product: 0, Delivery: 0, Packaging: 0, Trade: 0, Other: 0 };
let insightNotes = [];
let detectRisk = 0, detectMatches = 0, detectEscalations = 0, detectPositive = 0;

// ---- DOM ----
const DOM = {
  input: document.getElementById('complaint-input'),
  btn: document.getElementById('analyze-btn'),
  btnText: document.querySelector('.btn-text'),
  btnLoader: document.getElementById('btn-loader'),
  errorMsg: document.getElementById('error-msg'),
  results: document.getElementById('results-section'),
  grid: document.getElementById('results-grid'),
  pageTitle: document.getElementById('page-title'),
  historyBody: document.getElementById('history-body'),
  historyEmpty: document.getElementById('history-empty'),
  customerName: document.getElementById('customer-name'),
  orderId: document.getElementById('order-id'),
};

// ============================================================
// Navigation (hash-based — persists on refresh)
// ============================================================
const navButtons = document.querySelectorAll('.nav-item');
const views = document.querySelectorAll('.view');
const viewTitles = { dashboard: 'Dashboard', analyze: 'Analyze Complaint', history: 'Complaint History', insights: 'Insights', report: 'Report Generator' };

function switchView(target) {
  if (!viewTitles[target]) target = 'dashboard';
  navButtons.forEach(b => {
    b.classList.toggle('active', b.dataset.view === target);
  });
  views.forEach(v => v.classList.toggle('active', v.id === `view-${target}`));
  DOM.pageTitle.textContent = viewTitles[target] || 'Fixera';
}

navButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    const target = btn.dataset.view;
    window.location.hash = target;
    switchView(target);
  });
});

// Restore view from URL hash on load
const initialView = window.location.hash.replace('#', '') || 'dashboard';
switchView(initialView);

// Handle back/forward browser buttons
window.addEventListener('hashchange', () => {
  switchView(window.location.hash.replace('#', '') || 'dashboard');
});

// ============================================================
// Event Listeners
// ============================================================
DOM.btn.addEventListener('click', handleAnalyze);
DOM.input.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleAnalyze();
});

// Clear validation on input
document.querySelectorAll('#input-section input, #input-section textarea').forEach(el => {
  el.addEventListener('input', () => {
    el.classList.remove('input-error');
    const errEl = el.parentElement?.querySelector('.field-error') || (el.id === 'complaint-input' ? document.getElementById('err-text') : null);
    if (errEl) errEl.classList.add('hidden');
  });
});

// ============================================================
// Main Handler
// ============================================================
async function handleAnalyze() {
  // Clear previous validation
  document.querySelectorAll('.field-error').forEach(e => e.classList.add('hidden'));
  document.querySelectorAll('#input-section input, #input-section textarea').forEach(e => e.classList.remove('input-error'));

  const name = (DOM.customerName?.value || '').trim();
  const orderId = (DOM.orderId?.value || '').trim();
  const text = DOM.input.value.trim();

  // Validate required fields
  let hasError = false;
  if (!name) {
    document.getElementById('err-name')?.classList.remove('hidden');
    DOM.customerName?.classList.add('input-error');
    hasError = true;
  }
  if (!orderId) {
    document.getElementById('err-order')?.classList.remove('hidden');
    DOM.orderId?.classList.add('input-error');
    hasError = true;
  }
  if (!text) {
    document.getElementById('err-text')?.classList.remove('hidden');
    DOM.input?.classList.add('input-error');
    hasError = true;
  }
  if (hasError) {
    showError('Please fill all required fields.');
    return;
  }

  hideError();
  setLoading(true);

  try {
    const res = await fetch(PREDICT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, customer_name: name, order_id: orderId }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      throw new Error(errData?.error || `Server error (${res.status})`);
    }

    const data = await res.json();
    renderResults(data);
    // Refresh all dashboard data from backend
    await refreshDashboard();
  } catch (err) {
    showError(err.message || 'Something went wrong. Is the server running?');
  } finally {
    setLoading(false);
  }
}

// ============================================================
// Render Results
// ============================================================
function renderResults(data) {
  DOM.grid.innerHTML = '';

  const placeholder = document.getElementById('result-placeholder');
  if (placeholder) placeholder.style.display = 'none';

  // 1. Summary Row
  const summaryRow = document.createElement('div');
  summaryRow.className = 'result-summary-row';
  summaryRow.appendChild(buildSummaryItem('Category', data.category, 'category'));
  summaryRow.appendChild(buildSummaryItem('Priority', data.priority, 'priority'));
  summaryRow.appendChild(buildSummaryItem('Sentiment', data.sentiment, 'sentiment'));
  summaryRow.appendChild(buildSummaryItem('Status', data.status, 'status'));
  DOM.grid.appendChild(summaryRow);

  // 2. Recommendation (skip confidence bar and explanation — backend still computes them)
  const action = document.createElement('div');
  action.className = 'result-recommendation';
  action.innerHTML = `
    <div class="result-section-label">Recommended Action</div>
    <div class="recommendation-text">${data.action}</div>
    <div class="estimated-time">Estimated response: <strong>${data.estimated_time}</strong></div>`;
  DOM.grid.appendChild(action);

  // 5. System Insight
  const insights = generateInsights(data);
  if (insights.length) {
    const sec = document.createElement('div');
    sec.className = 'result-insight';
    sec.innerHTML = `<div class="result-section-label">System Insight</div><div class="insight-box">${insights.map(m => `<div class="insight-item">${m}</div>`).join('')}</div>`;
    DOM.grid.appendChild(sec);
  }

  // 6. Context Insight
  const ctx = generateContextInsights(data);
  if (ctx.length) {
    const sec = document.createElement('div');
    sec.className = 'result-context';
    sec.innerHTML = `<div class="result-section-label">Context Insight</div><div class="context-box">${ctx.map(m => `<div class="context-item">${m}</div>`).join('')}</div>`;
    DOM.grid.appendChild(sec);
  }

  DOM.results.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ============================================================
// Badge Builder
// ============================================================
function buildSummaryItem(label, value, type) {
  const item = document.createElement('div');
  item.className = 'summary-item';

  let bc = 'badge';
  if (type === 'priority') {
    bc += value === 'High' ? ' badge-danger' : value === 'Medium' ? ' badge-warning' : ' badge-success';
  } else if (type === 'sentiment') {
    bc += value === 'Negative' ? ' badge-danger' : value === 'Positive' ? ' badge-success' : ' badge-neutral';
  } else if (type === 'status') {
    bc += ' badge-status';
  } else {
    bc += ' badge-default';
  }

  item.innerHTML = `<div class="summary-label">${label}</div><span class="${bc}">${value}</span>`;
  return item;
}

// ============================================================
// Insight Generators
// ============================================================
function generateInsights(data) {
  const items = [];
  const r = (data.reason || '').toLowerCase();
  if (data.priority === 'High') items.push('⚠ This issue requires immediate attention and escalation.');
  if (r.includes('potential safety') || r.includes('critical issue')) items.push('🚨 Potential safety risk detected.');
  if (r.includes('similar complaints') || r.includes('similar past')) items.push('📊 Similar patterns observed in past data.');
  if (data.sentiment === 'Positive') items.push('✅ Positive feedback — no action required.');
  if (!items.length) items.push('ℹ Standard issue — normal workflow.');
  return items;
}

function generateContextInsights(data) {
  const items = [];
  if (data.priority === 'High') items.push('📈 High-priority: requires immediate operational attention.');
  const catMsg = { Product: '📊 Product issues impact customer trust.', Delivery: '🚚 Delivery delays are common complaints.', Packaging: '📦 Packaging issues may signal supply chain gaps.', Trade: '🏷️ Trade inquiries relate to bulk/partner accounts.' };
  if (catMsg[data.category]) items.push(catMsg[data.category]);
  if (data.confidence > 0.85) items.push('🔍 High confidence — strong historical match.');
  else if (data.confidence >= 0.6) items.push('🔎 Moderate confidence — partial match.');
  else items.push('⚠ Low confidence — limited data.');
  return items;
}

// ============================================================
// History
// ============================================================
function addToHistory(text, data) {
  history.unshift({ text, ...data });

  DOM.historyEmpty.style.display = 'none';

  const row = document.createElement('tr');
  const shortText = text.length > 50 ? text.slice(0, 50) + '…' : text;

  let priBadge = 'badge';
  priBadge += data.priority === 'High' ? ' badge-danger' : data.priority === 'Medium' ? ' badge-warning' : ' badge-success';

  row.innerHTML = `
    <td>${history.length}</td>
    <td><span class="text-truncate">${shortText}</span></td>
    <td>${data.category}</td>
    <td><span class="${priBadge}">${data.priority}</span></td>
    <td>${data.sentiment}</td>
    <td><span class="badge badge-timeline badge-timeline-${(data.priority || '').toLowerCase()}">${{ High: 'Within 12 hours', Medium: 'Within 48 hours', Low: 'Within 72 hours' }[data.priority] || 'N/A'}</span></td>`;

  DOM.historyBody.prepend(row);

  // Update dashboard recent (show last 3)
  const recent = document.getElementById('dashboard-recent');
  if (recent) {
    const items = history.slice(0, 3);
    recent.innerHTML = items.map(h => {
      const s = h.text.length > 60 ? h.text.slice(0, 60) + '…' : h.text;
      return `<div class="insight-row">${s} → <strong>${h.category}</strong> (${h.priority})</div>`;
    }).join('');
  }
}

// ============================================================
// Stats
// ============================================================
function updateStats(data) {
  stats.total++;
  if (data.priority === 'High') stats.high++;
  else if (data.priority === 'Medium') stats.medium++;
  else stats.low++;

  const cat = data.category in categoryCount ? data.category : 'Other';
  categoryCount[cat]++;

  document.getElementById('stat-total').textContent = stats.total;
  document.getElementById('stat-high').textContent = stats.high;
  document.getElementById('stat-medium').textContent = stats.medium;
  document.getElementById('stat-low').textContent = stats.low;
}

// ============================================================
// Insights Panel
// ============================================================
function updateInsights(data) {
  const r = (data.reason || '').toLowerCase();

  if (r.includes('safety') || r.includes('critical')) { detectRisk++; }
  if (r.includes('similar')) { detectMatches++; }
  if ((data.action || '').includes('ESCALATE')) { detectEscalations++; }
  if (data.sentiment === 'Positive') { detectPositive++; }

  document.getElementById('detect-risk').textContent = detectRisk;
  document.getElementById('detect-matches').textContent = detectMatches;
  document.getElementById('detect-escalations').textContent = detectEscalations;
  document.getElementById('detect-positive').textContent = detectPositive;

  // Build insight notes
  const list = document.getElementById('insights-list');
  const notes = [];

  if (detectRisk > 0) notes.push(`🚨 ${detectRisk} high-risk complaint(s) detected this session.`);
  if (detectEscalations > 0) notes.push(`⚠ ${detectEscalations} complaint(s) escalated for immediate review.`);
  if (categoryCount.Product > 2) notes.push('📈 Increase in product-related complaints observed.');
  if (categoryCount.Delivery > 2) notes.push('🚚 Multiple delivery complaints — possible logistics issue.');
  if (detectPositive > 0) notes.push(`✅ ${detectPositive} positive feedback received.`);
  if (stats.total > 0) notes.push(`📊 ${stats.total} total complaints analyzed this session.`);

  if (notes.length) {
    list.innerHTML = notes.map(n => `<div class="insight-row">${n}</div>`).join('');
  }
}

// ============================================================
// Charts (Dashboard + Insights)
// ============================================================
let chartCategory = null;
let chartPriority = null;
let insChartSent = null, insChartTrend = null, insChartCrit = null;

const FONT = "'Inter', sans-serif";
const GRID_C = '#f0f0f2';
const TICK_C = '#6b7280';

function barOpts(hideLegend) {
  return {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: !hideLegend } },
    scales: {
      y: { beginAtZero: true, ticks: { stepSize: 1, font: { family: FONT, size: 10 }, color: TICK_C }, grid: { color: GRID_C }, border: { display: false } },
      x: { ticks: { font: { family: FONT, size: 10 }, color: TICK_C }, grid: { display: false }, border: { display: false } },
    }
  };
}

function doughnutOpts(cutout) {
  return {
    responsive: true, maintainAspectRatio: false, cutout: cutout || '65%',
    plugins: { legend: { position: 'bottom', labels: { font: { family: FONT, size: 11 }, color: TICK_C, padding: 14, usePointStyle: true, pointStyleWidth: 8 } } }
  };
}

function initCharts() {
  if (typeof Chart === 'undefined') return;

  // --- Dashboard charts ---
  const ctxCat = document.getElementById('chart-category');
  const ctxPri = document.getElementById('chart-priority');

  if (ctxCat) {
    chartCategory = new Chart(ctxCat, {
      type: 'bar',
      data: { labels: ['Product', 'Delivery', 'Packaging', 'Trade', 'Other'], datasets: [{ label: 'Complaints', data: [0, 0, 0, 0, 0], backgroundColor: ['#6366f1', '#3b82f6', '#f59e0b', '#8b5cf6', '#94a3b8'], borderRadius: 6, barThickness: 32, maxBarThickness: 40 }] },
      options: barOpts(true),
    });
  }

  if (ctxPri) {
    chartPriority = new Chart(ctxPri, {
      type: 'doughnut',
      data: { labels: ['High', 'Medium', 'Low'], datasets: [{ data: [0, 0, 0], backgroundColor: ['#ef4444', '#f59e0b', '#10b981'], borderWidth: 2, borderColor: '#fff' }] },
      options: doughnutOpts('65%'),
    });
  }

  // --- Insight charts (unique to Insights page) ---
  const ic3 = document.getElementById('ins-chart-sentiment');
  const ic4 = document.getElementById('ins-chart-trend');
  const ic5 = document.getElementById('ins-chart-critical');

  if (ic3) {
    insChartSent = new Chart(ic3, {
      type: 'doughnut',
      data: { labels: ['Negative', 'Neutral', 'Positive'], datasets: [{ data: [0, 0, 0], backgroundColor: ['#ef4444', '#94a3b8', '#10b981'], borderWidth: 2, borderColor: '#fff' }] },
      options: doughnutOpts('60%'),
    });
  }

  if (ic4) {
    insChartTrend = new Chart(ic4, {
      type: 'line',
      data: { labels: [], datasets: [{ label: 'Cumulative', data: [], borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,.08)', fill: true, tension: 0.3, pointRadius: 2, pointBackgroundColor: '#2563eb' }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: { stepSize: 1, font: { family: FONT, size: 10 }, color: TICK_C }, grid: { color: GRID_C }, border: { display: false } },
          x: { ticks: { font: { family: FONT, size: 9 }, color: TICK_C, maxTicksLimit: 10 }, grid: { display: false }, border: { display: false } },
        }
      }
    });
  }

  if (ic5) {
    insChartCrit = new Chart(ic5, {
      type: 'bar',
      data: {
        labels: [],
        datasets: [{
          label: 'Complaints',
          data: [],
          backgroundColor: 'rgba(37,99,235,0.7)',
          borderRadius: 6,
          barThickness: 'flex',
          maxBarThickness: 32,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: { stepSize: 1, font: { family: FONT, size: 10 }, color: TICK_C }, grid: { color: GRID_C }, border: { display: false } },
          x: { ticks: { font: { family: FONT, size: 9 }, color: TICK_C, maxRotation: 45 }, grid: { display: false }, border: { display: false } },
        }
      }
    });
  }
}

function updateCharts() {
  if (chartCategory) {
    chartCategory.data.datasets[0].data = [categoryCount.Product, categoryCount.Delivery, categoryCount.Packaging, categoryCount.Trade, categoryCount.Other];
    chartCategory.update();
  }
  if (chartPriority) {
    chartPriority.data.datasets[0].data = [stats.high, stats.medium, stats.low];
    chartPriority.update();
  }
}

function updateInsightCharts(sentimentCounts, complaints) {
  // Sentiment
  if (insChartSent) {
    insChartSent.data.datasets[0].data = [sentimentCounts.Negative || 0, sentimentCounts.Neutral || 0, sentimentCounts.Positive || 0];
    insChartSent.update();
  }

  // Trend (cumulative)
  if (insChartTrend && complaints.length > 0) {
    const reversed = [...complaints].reverse();
    const labels = reversed.map((_, i) => `#${i + 1}`);
    const cumulative = reversed.map((_, i) => i + 1);
    insChartTrend.data.labels = labels;
    insChartTrend.data.datasets[0].data = cumulative;
    insChartTrend.update();
  }

  // Complaints Per Hour
  if (insChartCrit && complaints.length > 0) {
    const hourCounts = {};
    complaints.forEach(c => {
      if (c.timestamp) {
        try {
          const d = new Date(c.timestamp);
          const key = d.toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', hour12: false });
          hourCounts[key] = (hourCounts[key] || 0) + 1;
        } catch (e) {}
      }
    });
    const entries = Object.entries(hourCounts).reverse();
    insChartCrit.data.labels = entries.map(e => e[0]);
    insChartCrit.data.datasets[0].data = entries.map(e => e[1]);
    insChartCrit.update();
  }

  // Empty state
  const emptyEl = document.getElementById('insights-empty');
  const contentEl = document.getElementById('insights-content');
  if (emptyEl && contentEl) {
    if (stats.total === 0) {
      emptyEl.style.display = '';
      contentEl.style.display = 'none';
    } else {
      emptyEl.style.display = 'none';
      contentEl.style.display = '';
    }
  }
}

// ============================================================
// Helpers
// ============================================================
function setLoading(on) {
  DOM.btn.disabled = on;
  DOM.btnText.textContent = on ? 'Analyzing…' : 'Analyze Complaint';
  DOM.btnLoader.classList.toggle('hidden', !on);
}

function showError(msg) {
  DOM.errorMsg.textContent = msg;
  DOM.errorMsg.classList.remove('hidden');
  DOM.grid.innerHTML = '';
  const p = document.getElementById('result-placeholder');
  if (p) p.style.display = '';
}

function hideError() {
  DOM.errorMsg.classList.add('hidden');
}

// ============================================================
// Status Change Handler (Lifecycle Management)
// ============================================================
async function handleStatusChange(selectEl) {
  const id = selectEl.dataset.id;
  const newStatus = selectEl.value;

  try {
    const res = await fetch('/update_status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: parseInt(id), status: newStatus })
    });
    const data = await res.json();

    if (!res.ok) {
      alert('❌ ' + (data.error || 'Failed to update status'));
      // Revert dropdown to old value
      refreshDashboard();
      return;
    }

    // Show warning if applicable
    if (data.warning) {
      alert('⚠️ Warning: ' + data.warning);
    }

    // Refresh to update timeline and SLA columns
    refreshDashboard();
  } catch (e) {
    alert('❌ Network error: ' + e.message);
    refreshDashboard();
  }
}

// Make it available globally for inline onchange
window.handleStatusChange = handleStatusChange;

// ============================================================
// History Row Renderer
// ============================================================
function renderHistoryRow(c, i, total, extraClass) {
  history.push(c);
  const row = document.createElement('tr');
  if (extraClass) row.className = extraClass;
  const shortText = c.text.length > 50 ? c.text.slice(0, 50) + '…' : c.text;
  let priBadge = 'badge';
  priBadge += c.priority === 'High' ? ' badge-danger' : c.priority === 'Medium' ? ' badge-warning' : ' badge-success';

  // Status dropdown
  const statusOpts = ['Pending', 'In Progress', 'Resolved', 'Closed', 'Ignored'];
  const currentStatus = c.status || 'Pending';
  const statusSelect = statusOpts.map(s =>
    `<option value="${s}" ${s === currentStatus ? 'selected' : ''}>${s}</option>`
  ).join('');

  // Timeline info
  const timeInfo = c.time_info || '';

  // SLA indicator
  const slaHtml = c.sla_breached
    ? '<span class="badge badge-danger" style="font-size:0.7rem;">⚠ SLA Breached</span>'
    : '<span class="badge badge-success" style="font-size:0.7rem;">✓ On Track</span>';

  row.innerHTML = `
    <td>${total - i}</td>
    <td title="${c.customer_name || 'N/A'}">${(c.customer_name || 'N/A').slice(0, 20)}</td>
    <td>${c.order_id || 'N/A'}</td>
    <td><span class="text-truncate">${shortText}</span></td>
    <td>${c.category}</td>
    <td><span class="${priBadge}">${c.priority}</span></td>
    <td>
      <select class="status-dropdown" data-id="${c.id}" data-priority="${c.priority}" data-created="${c.timestamp || ''}" onchange="handleStatusChange(this)">
        ${statusSelect}
      </select>
    </td>
    <td><span class="badge badge-timeline">${timeInfo || 'N/A'}</span></td>
    <td>${c.status === 'Ignored' ? '<span style="color:var(--text-faint);font-size:0.75rem;">—</span>' : slaHtml}</td>`;
  DOM.historyBody.appendChild(row);
}

// ============================================================
// Init — Load persisted data
// ============================================================
initCharts();

async function refreshDashboard() {
  try {
    // --- Reset all local state ---
    stats.total = 0; stats.high = 0; stats.medium = 0; stats.low = 0;
    Object.keys(categoryCount).forEach(k => categoryCount[k] = 0);
    history.length = 0;
    detectRisk = 0; detectMatches = 0; detectEscalations = 0; detectPositive = 0;
    DOM.historyBody.innerHTML = '';

    // --- Fetch stats ---
    const statsRes = await fetch('/stats');
    if (statsRes.ok) {
      const s = await statsRes.json();
      stats.total = s.total || 0;
      stats.high = (s.by_priority && s.by_priority.High) || 0;
      stats.medium = (s.by_priority && s.by_priority.Medium) || 0;
      stats.low = (s.by_priority && s.by_priority.Low) || 0;

      document.getElementById('stat-total').textContent = stats.total;
      document.getElementById('stat-high').textContent = stats.high;
      document.getElementById('stat-medium').textContent = stats.medium;
      document.getElementById('stat-low').textContent = stats.low;

      if (s.by_category) {
        Object.keys(s.by_category).forEach(k => {
          if (k in categoryCount) categoryCount[k] = s.by_category[k];
          else categoryCount.Other = (categoryCount.Other || 0) + s.by_category[k];
        });
      }

      // Store combined sentiment from stats
      stats.by_sentiment = s.by_sentiment || {};

      updateCharts();
    }

    // --- Fetch complaints ---
    const compRes = await fetch('/complaints');
    if (compRes.ok) {
      const complaints = await compRes.json();

      if (complaints.length > 0) {
        DOM.historyEmpty.style.display = 'none';
      } else {
        DOM.historyEmpty.style.display = '';
      }

      // Separate active lifecycle complaints from the rest
      const activeLifecycle = complaints.filter(c => ['In Progress', 'Resolved'].includes(c.status));
      const otherComplaints = complaints.filter(c => !['In Progress', 'Resolved'].includes(c.status));

      // Render active lifecycle section first
      if (activeLifecycle.length > 0) {
        const headerRow = document.createElement('tr');
        headerRow.innerHTML = `<td colspan="9" class="lifecycle-header">🔄 Active Lifecycle — ${activeLifecycle.length} complaint${activeLifecycle.length !== 1 ? 's' : ''} in progress</td>`;
        DOM.historyBody.appendChild(headerRow);

        activeLifecycle.forEach((c, i) => renderHistoryRow(c, i, activeLifecycle.length, 'lifecycle-row'));

        // Separator
        const sepRow = document.createElement('tr');
        sepRow.innerHTML = `<td colspan="9" class="lifecycle-separator">All Complaints</td>`;
        DOM.historyBody.appendChild(sepRow);
      }

      // Render rest
      otherComplaints.forEach((c, i) => renderHistoryRow(c, i, otherComplaints.length, ''));

      // Combined insight metrics from ALL complaints
      complaints.forEach(c => {
        const r = (c.reason || '').toLowerCase();
        if (r.includes('safety') || r.includes('critical')) detectRisk++;
        if (r.includes('similar')) detectMatches++;
        if ((c.action || '').includes('ESCALATE')) detectEscalations++;
        if (c.sentiment === 'Positive') detectPositive++;
      });

      // --- Show report history at bottom ---
      try {
        const rptRes = await fetch('/report_history');
        if (rptRes.ok) {
          const reports = await rptRes.json();
          if (reports.length > 0) {
            DOM.historyEmpty.style.display = 'none';
            // Add separator
            const sepRow = document.createElement('tr');
            sepRow.innerHTML = `<td colspan="9" class="lifecycle-separator">Report History</td>`;
            DOM.historyBody.appendChild(sepRow);

            reports.forEach(rpt => {
              const row = document.createElement('tr');
              row.style.background = 'rgba(37,99,235,0.04)';
              const date = rpt.created_at ? new Date(rpt.created_at).toLocaleString() : '';
              row.innerHTML = `
                <td><span class="badge" style="background:#eef2ff;color:#2563eb;font-size:0.7rem;">Report</span></td>
                <td colspan="2"><span class="text-truncate">${rpt.filename}</span></td>
                <td style="font-size:0.8rem;color:var(--text-muted);">${date}</td>
                <td><strong>${rpt.total_complaints}</strong> complaints</td>
                <td style="font-size:0.78rem;">H:${rpt.high_count || 0} M:${rpt.medium_count || 0} L:${rpt.low_count || 0}</td>
                <td></td>
                <td></td>
                <td><span class="badge badge-timeline">Bulk analysis</span></td>`;
              DOM.historyBody.appendChild(row);
            });
          }
        }
      } catch (e) { /* report history optional */ }

      // Count sentiments
      const sentimentCounts = {};
      complaints.forEach(c => {
        sentimentCounts[c.sentiment] = (sentimentCounts[c.sentiment] || 0) + 1;
      });

      // Update detection counters
      document.getElementById('detect-risk').textContent = detectRisk;
      document.getElementById('detect-matches').textContent = detectMatches;
      document.getElementById('detect-escalations').textContent = detectEscalations;
      document.getElementById('detect-positive').textContent = detectPositive;

      // Dashboard recent (last 3)
      const recent = document.getElementById('dashboard-recent');
      if (recent) {
        if (complaints.length > 0) {
          const items = complaints.slice(0, 3);
          recent.innerHTML = items.map(h => {
            const s = h.text.length > 60 ? h.text.slice(0, 60) + '…' : h.text;
            return `<div class="insight-row">${s} → <strong>${h.category}</strong> (${h.priority})</div>`;
          }).join('');
        } else {
          recent.innerHTML = '<p class="empty-state">No complaints analyzed yet. Go to Analyze to get started.</p>';
        }
      }

      // --- Data-Driven Insights (numbers only, no vague text) ---
      const list = document.getElementById('insights-list');
      if (stats.total > 0) {
        const notes = [];
        const pct = (n) => stats.total > 0 ? Math.round((n / stats.total) * 100) : 0;

        // Most common category
        const catEntries = Object.entries(categoryCount).filter(([, v]) => v > 0);
        if (catEntries.length > 0) {
          catEntries.sort((a, b) => b[1] - a[1]);
          const [topCat, topCount] = catEntries[0];
          notes.push(`📊 ${topCat} complaints: ${topCount} out of ${stats.total} total (${pct(topCount)}%)`);
          if (catEntries.length > 1) {
            const [cat2, cnt2] = catEntries[1];
            notes.push(`📦 ${cat2} issues rank #2 with ${cnt2} complaint${cnt2 !== 1 ? 's' : ''} (${pct(cnt2)}%)`);
          }
        }

        // Priority breakdown
        if (stats.high > 0) notes.push(`🚨 High-priority cases: ${stats.high} out of ${stats.total} (${pct(stats.high)}%)`);
        if (stats.medium > 0) notes.push(`⚠ Medium-priority cases: ${stats.medium} out of ${stats.total} (${pct(stats.medium)}%)`);
        if (stats.low > 0) notes.push(`✅ Low-priority cases: ${stats.low} out of ${stats.total} (${pct(stats.low)}%)`);

        // Sentiment (use combined stats)
        const neg = (stats.by_sentiment && stats.by_sentiment.Negative) || sentimentCounts.Negative || 0;
        const pos = (stats.by_sentiment && stats.by_sentiment.Positive) || sentimentCounts.Positive || 0;
        if (neg > 0) notes.push(`😠 Negative sentiment: ${neg} complaint${neg !== 1 ? 's' : ''} (${pct(neg)}%)`);
        if (pos > 0) notes.push(`😊 Positive sentiment: ${pos} feedback${pos !== 1 ? 's' : ''} (${pct(pos)}%)`);

        // Escalation
        if (detectEscalations > 0) notes.push(`🔺 ${detectEscalations} case${detectEscalations !== 1 ? 's' : ''} escalated for immediate review`);
        if (detectMatches > 0) notes.push(`🔍 ${detectMatches} complaint${detectMatches !== 1 ? 's' : ''} matched with historical dataset patterns`);

        notes.push(`📋 Total analyzed: ${stats.total} complaint${stats.total !== 1 ? 's' : ''}`);
        list.innerHTML = notes.map(n => `<div class="insight-row">${n}</div>`).join('');
      } else {
        list.innerHTML = '<div class="insight-row">📊 No complaint data available yet.</div>';
      }

      // Use combined sentiment from stats for insight charts
      const combinedSentiment = stats.by_sentiment || sentimentCounts;

      // Update insight charts with combined data
      updateInsightCharts(combinedSentiment, complaints);
    }
  } catch (e) {
    console.log('[Fixera] Could not load data:', e);
  }
}

refreshDashboard();

// ============================================================
// Report Generator (Enhanced)
// ============================================================
(function initReportGenerator() {
  const genBtn = document.getElementById('report-generate-btn');
  const emailBtn = document.getElementById('report-use-email-btn');
  const dropZone = document.getElementById('report-drop-zone');
  const fileInput = document.getElementById('report-csv-upload');
  const fileNameEl = document.getElementById('report-file-name');
  if (!genBtn) return;

  // --- Drag & Drop ---
  if (dropZone && fileInput) {
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('dragging');
    });
    dropZone.addEventListener('dragleave', () => {
      dropZone.classList.remove('dragging');
    });
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragging');
      if (e.dataTransfer.files.length) {
        fileInput.files = e.dataTransfer.files;
        fileNameEl.textContent = e.dataTransfer.files[0].name;
        fileNameEl.classList.remove('hidden');
      }
    });
    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) {
        fileNameEl.textContent = fileInput.files[0].name;
        fileNameEl.classList.remove('hidden');
      }
    });
  }

  // --- Generate Report ---
  async function generateReport(useEmailData) {
    const btnText = genBtn.querySelector('.btn-text');
    const loader = document.getElementById('report-btn-loader');
    const errMsg = document.getElementById('report-error-msg');
    const banner = document.getElementById('report-success-banner');
    const successTitle = document.getElementById('report-success-title');
    const successDetail = document.getElementById('report-success-detail');
    const downloadLink = document.getElementById('report-download-link');
    const previewStats = document.getElementById('report-preview-stats');
    const statCards = document.getElementById('report-stat-cards');
    const previewText = document.getElementById('report-preview-text');

    // Reset
    btnText.textContent = '⏳ Generating...';
    loader && loader.classList.remove('hidden');
    errMsg && errMsg.classList.add('hidden');
    banner && banner.classList.add('hidden');
    downloadLink && downloadLink.classList.add('hidden');
    genBtn.disabled = true;

    try {
      const formData = new FormData();
      const hasFile = fileInput && fileInput.files.length > 0;

      // Strict validation: must have file OR email data
      if (!useEmailData && !hasFile) {
        throw new Error('Please upload a CSV file or click "Use Email Data" first.');
      }

      if (useEmailData) {
        formData.append('use_email_data', 'true');
      } else {
        formData.append('file', fileInput.files[0]);
      }

      const resp = await fetch('/generate_report', { method: 'POST', body: formData });
      const data = await resp.json();

      if (!resp.ok) throw new Error(data.error || 'Failed to generate report');

      // Success banner
      successTitle.textContent = 'Report generated successfully';
      successDetail.textContent = `${data.total} complaints analyzed · ${data.high || 0} high priority`;
      banner.classList.remove('hidden');

      // Download link
      downloadLink.href = data.file;
      downloadLink.classList.remove('hidden');
      previewText.textContent = `${data.total} complaints analyzed · ${data.high || 0} high priority`;

      // Fade out placeholder, fade in stats
      const placeholder = document.getElementById('report-placeholder');
      if (placeholder) placeholder.classList.add('fade-out');

      // Preview stat cards
      previewStats.classList.remove('hidden');
      statCards.innerHTML = `
        <div class="rpt-stat rpt-stat-total"><div class="rpt-stat-number">${data.total}</div><div class="rpt-stat-label">Total</div></div>
        <div class="rpt-stat rpt-stat-high"><div class="rpt-stat-number">${data.high || 0}</div><div class="rpt-stat-label">High</div></div>
        <div class="rpt-stat rpt-stat-medium"><div class="rpt-stat-number">${data.medium || 0}</div><div class="rpt-stat-label">Medium</div></div>
        <div class="rpt-stat rpt-stat-low"><div class="rpt-stat-number">${data.low || 0}</div><div class="rpt-stat-label">Low</div></div>
      `;

      // Trigger fade-in after a tiny delay
      setTimeout(() => previewStats.classList.add('visible'), 50);

      // Refresh history
      loadReportHistory();

    } catch (e) {
      errMsg.textContent = '❌ ' + e.message;
      errMsg.classList.remove('hidden');
    } finally {
      btnText.textContent = 'Generate Report';
      loader && loader.classList.add('hidden');
      genBtn.disabled = false;
    }
  }

  genBtn.addEventListener('click', () => generateReport(false));
  emailBtn && emailBtn.addEventListener('click', async () => {
    const errMsg = document.getElementById('report-error-msg');
    const previewText = document.getElementById('report-preview-text');
    try {
      errMsg && errMsg.classList.add('hidden');
      emailBtn.disabled = true;
      emailBtn.textContent = '📧 Fetching emails…';
      const check = await fetch('/use-email-data');
      const info = await check.json();
      if (!check.ok || info.error) {
        throw new Error(info.error || 'No email data available');
      }
      if (previewText) previewText.textContent = `✅ ${info.rows} complaint(s) fetched from Gmail`;
      emailBtn.textContent = '⏳ Generating report…';
      await generateReport(true);
    } catch (e) {
      if (errMsg) { errMsg.textContent = '❌ ' + e.message; errMsg.classList.remove('hidden'); }
    } finally {
      emailBtn.disabled = false;
      emailBtn.textContent = 'Use Email Data';
    }
  });

  // --- Report History ---
  async function loadReportHistory() {
    try {
      const resp = await fetch('/report_history');
      const reports = await resp.json();
      const tbody = document.getElementById('report-history-body');
      if (!tbody) return;

      if (!reports.length || reports.error) {
        tbody.innerHTML = `<tr class="rpt-empty-row"><td colspan="8">
          <div class="rpt-empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="36" height="36"><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
            <p class="rpt-empty-title">No reports yet</p>
            <p class="rpt-empty-hint">Generate your first report to see history here</p>
          </div>
        </td></tr>`;
        return;
      }

      tbody.innerHTML = reports.map(r => {
        const date = r.created_at ? new Date(r.created_at).toLocaleString() : '—';
        return `<tr>
          <td>${r.id}</td>
          <td class="rpt-report-name">${r.filename}</td>
          <td class="rpt-date">${date}</td>
          <td><strong>${r.total_complaints}</strong></td>
          <td><span class="rpt-badge rpt-badge-high">${r.high_count || 0}</span></td>
          <td><span class="rpt-badge rpt-badge-medium">${r.medium_count || 0}</span></td>
          <td><span class="rpt-badge rpt-badge-low">${r.low_count || 0}</span></td>
          <td><a class="rpt-dl-btn" href="/download_report/${r.id}" download title="Download">
            <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
          </a></td>
        </tr>`;
      }).join('');
    } catch (e) {
      console.log('[Fixera] Could not load report history:', e);
    }
  }

  // Load on page init
  loadReportHistory();
})();

// ============================================================
// Auto-Refresh — Dashboard & Insights update every 6 seconds
// ============================================================
(function autoRefresh() {
  let refreshing = false;
  const INTERVAL_MS = 6000;

  function getActiveView() {
    return (window.location.hash.replace('#', '') || 'dashboard');
  }

  async function tick() {
    if (refreshing) return;
    if (document.visibilityState !== 'visible') return;
    // Only auto-refresh when on dashboard — prevents history scroll reset
    if (getActiveView() !== 'dashboard') return;
    refreshing = true;
    try {
      await refreshDashboard();
    } catch (e) { /* silent */ }
    refreshing = false;
  }

  setInterval(tick, INTERVAL_MS);

  // Refresh immediately when tab becomes visible again
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && getActiveView() === 'dashboard') tick();
  });
})();
