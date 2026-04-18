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

// ---- Label config for result tiles ----
const TILE_CONFIG = [
  { key: 'category',       label: 'Category',       icon: '📂' },
  { key: 'priority',       label: 'Priority',       icon: '🔥' },
  { key: 'sentiment',      label: 'Sentiment',      icon: '💬' },
  { key: 'confidence',     label: 'Confidence',     icon: '📊' },
  { key: 'reason',         label: 'Reason',         icon: '🔍' },
  { key: 'action',         label: 'Action',         icon: '🛠️' },
  { key: 'status',         label: 'Status',         icon: '📋' },
  { key: 'estimated_time', label: 'Est. Response',  icon: '⏱️' },
];

// ---- Event Listeners ----
DOM.btn.addEventListener('click', handleAnalyze);
DOM.input.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleAnalyze();
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

  TILE_CONFIG.forEach((tile, i) => {
    const value = data[tile.key];
    if (value === undefined) return;

    const el = document.createElement('div');
    el.className = 'result-tile';
    el.style.animationDelay = `${i * 0.06}s`;

    // Special handling for confidence (show bar)
    if (tile.key === 'confidence') {
      const pct = Math.round(value * 100);
      el.innerHTML = `
        <div class="tile-label">${tile.icon} ${tile.label}</div>
        <div class="tile-value">${pct}%</div>
        <div class="confidence-bar-bg">
          <div class="confidence-bar-fill" style="width: 0%"></div>
        </div>
      `;
      DOM.grid.appendChild(el);
      // Animate bar after paint
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          el.querySelector('.confidence-bar-fill').style.width = `${pct}%`;
        });
      });
      return;
    }

    el.innerHTML = `
      <div class="tile-label">${tile.icon} ${tile.label}</div>
      <div class="tile-value"
           ${tile.key === 'sentiment' ? `data-sentiment="${value}"` : ''}
           ${tile.key === 'priority'  ? `data-priority="${value}"`  : ''}
      >${value}</div>
    `;

    DOM.grid.appendChild(el);
  });

  DOM.results.classList.remove('hidden');
  DOM.results.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
  DOM.results.classList.add('hidden');
}

function hideError() {
  DOM.errorMsg.classList.add('hidden');
}
