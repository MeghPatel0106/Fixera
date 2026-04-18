// ============================================================
// Fixera — Frontend Logic
// ============================================================

const PREDICT_URL = '/predict';

const DOM = {
  input:    document.getElementById('complaint-input'),
  btn:      document.getElementById('analyze-btn'),
  btnText:  document.querySelector('.btn-text'),
  btnLoader: document.getElementById('btn-loader'),
  errorMsg: document.getElementById('error-msg'),
  results:  document.getElementById('results-section'),
  grid:     document.getElementById('results-grid'),
};

// ---- Event Listeners ----
DOM.btn.addEventListener('click', handleAnalyze);
DOM.input.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleAnalyze();
});

// ---- Example Buttons ----
document.querySelectorAll('.example-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    DOM.input.value = btn.getAttribute('data-text');
    DOM.input.focus();
  });
});

// ---- Main Handler ----
async function handleAnalyze() {
  const text = DOM.input.value.trim();

  // Validate
  if (!text) {
    showError('Please enter a complaint before analyzing.');
    return;
  }

  hideError();
  setLoading(true);

  try {
    const res = await fetch(PREDICT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      throw new Error(errData?.error || `Server error (${res.status})`);
    }

    const data = await res.json();
    renderResults(data);
  } catch (err) {
    showError(err.message || 'Something went wrong. Is the server running?');
  } finally {
    setLoading(false);
  }
}

// ---- Render Results ----
function renderResults(data) {
  DOM.grid.innerHTML = '';

  // Hide placeholder text
  const placeholder = document.getElementById('result-placeholder');
  if (placeholder) placeholder.style.display = 'none';

  // --- 1. Summary Row: Category, Priority, Sentiment, Status ---
  const summaryRow = document.createElement('div');
  summaryRow.className = 'result-summary-row';

  summaryRow.appendChild(buildSummaryItem('Category', data.category, 'category'));
  summaryRow.appendChild(buildSummaryItem('Priority', data.priority, 'priority'));
  summaryRow.appendChild(buildSummaryItem('Sentiment', data.sentiment, 'sentiment'));
  summaryRow.appendChild(buildSummaryItem('Status', data.status, 'status'));

  DOM.grid.appendChild(summaryRow);

  // --- 2. Confidence ---
  const pct = Math.round(data.confidence * 100);
  const confidenceSection = document.createElement('div');
  confidenceSection.className = 'result-confidence';
  confidenceSection.innerHTML = `
    <div class="result-section-label">Confidence</div>
    <div class="confidence-row">
      <div class="confidence-bar-bg">
        <div class="confidence-bar-fill" style="width: 0%"></div>
      </div>
      <span class="confidence-pct">${pct}%</span>
    </div>
  `;
  DOM.grid.appendChild(confidenceSection);

  // Animate bar after paint
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      confidenceSection.querySelector('.confidence-bar-fill').style.width = `${pct}%`;
    });
  });

  // --- 3. Explanation ---
  const reasonSection = document.createElement('div');
  reasonSection.className = 'result-explanation';
  reasonSection.innerHTML = `
    <div class="result-section-label">Why this decision was made</div>
    <div class="explanation-box">${data.reason}</div>
  `;
  DOM.grid.appendChild(reasonSection);

  // --- 4. Recommendation ---
  const actionSection = document.createElement('div');
  actionSection.className = 'result-recommendation';
  actionSection.innerHTML = `
    <div class="result-section-label">Recommended Action</div>
    <div class="recommendation-text">${data.action}</div>
    <div class="estimated-time">Estimated response time: <strong>${data.estimated_time}</strong></div>
  `;
  DOM.grid.appendChild(actionSection);

  // --- 5. System Insight ---
  const insights = generateInsights(data);
  if (insights.length > 0) {
    const insightSection = document.createElement('div');
    insightSection.className = 'result-insight';
    insightSection.innerHTML = `
      <div class="result-section-label">System Insight</div>
      <div class="insight-box">
        ${insights.map(msg => `<div class="insight-item">${msg}</div>`).join('')}
      </div>
    `;
    DOM.grid.appendChild(insightSection);
  }

  DOM.results.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ---- Build a single summary item with badge ----
function buildSummaryItem(label, value, type) {
  const item = document.createElement('div');
  item.className = 'summary-item';

  let badgeClass = 'badge';
  if (type === 'priority') {
    if (value === 'High') badgeClass += ' badge-danger';
    else if (value === 'Medium') badgeClass += ' badge-warning';
    else badgeClass += ' badge-success';
  } else if (type === 'sentiment') {
    if (value === 'Negative') badgeClass += ' badge-danger';
    else if (value === 'Positive') badgeClass += ' badge-success';
    else badgeClass += ' badge-neutral';
  } else if (type === 'status') {
    badgeClass += ' badge-status';
  } else {
    badgeClass += ' badge-default';
  }

  item.innerHTML = `
    <div class="summary-label">${label}</div>
    <span class="${badgeClass}">${value}</span>
  `;
  return item;
}

// ---- Generate Insight Messages ----
function generateInsights(data) {
  const insights = [];
  const reasonLower = (data.reason || '').toLowerCase();

  if (data.priority === 'High') {
    insights.push('⚠ This issue requires immediate attention and escalation.');
  }

  if (reasonLower.includes('potential safety') || reasonLower.includes('critical issue')) {
    insights.push('🚨 This complaint indicates a potential safety risk.');
  }

  if (reasonLower.includes('similar complaints') || reasonLower.includes('similar past')) {
    insights.push('📊 Similar complaint patterns have been observed in past data.');
  }

  if (data.sentiment === 'Positive') {
    insights.push('✅ Positive feedback — no action required.');
  }

  if (insights.length === 0) {
    insights.push('ℹ Standard issue — can be handled in normal workflow.');
  }

  return insights;
}

// ---- Helpers ----
function setLoading(on) {
  DOM.btn.disabled = on;
  DOM.btnText.textContent = on ? 'Analyzing…' : 'Analyze';
  DOM.btnLoader.classList.toggle('hidden', !on);
}

function showError(msg) {
  DOM.errorMsg.textContent = msg;
  DOM.errorMsg.classList.remove('hidden');
  DOM.grid.innerHTML = '';
  const placeholder = document.getElementById('result-placeholder');
  if (placeholder) placeholder.style.display = '';
}

function hideError() {
  DOM.errorMsg.classList.add('hidden');
}
