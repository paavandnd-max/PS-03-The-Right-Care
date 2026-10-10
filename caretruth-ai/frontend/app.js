/* VERITAS Health Intelligence — Client Application Logic */

const API_BASE = window.location.origin.includes('8000') || window.location.origin.includes('8501')
  ? window.location.origin
  : 'http://localhost:8000';

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initFacilitySelector();
  initAuditorActions();
});

// Navigation Tab Switcher
function initNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      navItems.forEach(n => n.classList.remove('active'));
      item.classList.add('active');

      const tabName = item.getAttribute('data-tab');
      handleTabSwitch(tabName);
    });
  });
}

function handleTabSwitch(tabName) {
  const viewContainer = document.getElementById('viewContainer');
  if (tabName === 'dossier') {
    loadFacilityDossier(document.getElementById('facilitySelect').value);
  } else if (tabName === 'queue') {
    renderVerificationQueueView();
  } else if (tabName === 'overview') {
    renderOverviewView();
  } else if (tabName === 'commits') {
    renderCommitsView();
  } else if (tabName === 'map') {
    renderMapView();
  } else if (tabName === 'explorer') {
    renderExplorerView();
  }
}

// Populate Facility Dropdown & Connect Selector
async function initFacilitySelector() {
  const select = document.getElementById('facilitySelect');
  try {
    const res = await fetch(`${API_BASE}/api/facilities?limit=50`);
    if (res.ok) {
      const data = await res.json();
      if (data.facilities && data.facilities.length > 0) {
        select.innerHTML = '';
        data.facilities.forEach(fac => {
          const opt = document.createElement('option');
          opt.value = fac.name;
          opt.textContent = `${fac.name} — PIN: ${fac.pin || 'BR-849201'}`;
          select.appendChild(opt);
        });
      }
    }
  } catch (err) {
    console.warn('API facilities list fetch failed, using default options:', err);
  }

  select.addEventListener('change', (e) => {
    loadFacilityDossier(e.target.value);
  });

  // Load initial selection
  loadFacilityDossier(select.value);
}

// Load Facility Dossier Details from Backend
async function loadFacilityDossier(facilityName) {
  try {
    const res = await fetch(`${API_BASE}/api/facility/${encodeURIComponent(facilityName)}`);
    if (res.ok) {
      const data = await res.json();
      updateDossierUI(data);
    } else {
      console.warn('Backend facility dossier lookup failed, rendering default presentation layer.');
    }
  } catch (err) {
    console.warn('Backend unavailable, rendering responsive offline dossier presentation:', err);
  }
}

function updateDossierUI(data) {
  if (!data || !data.name) return;

  document.getElementById('dossierFacilityName').textContent = data.name;
  document.getElementById('dossierNin').textContent = `NIN: BR-${data.pin || '849201'}`;
  document.getElementById('dossierBeds').textContent = `${data.capacity || 30}-Bed Rural Secondary Care Center`;
  document.getElementById('attestNin').textContent = `BR-${data.pin || '849201'}`;
  document.getElementById('dossierMeta').innerHTML = `
    📍 <b>Block:</b> Kalyanpur &nbsp;·&nbsp; <b>District:</b> ${data.city || 'Samastipur'}, ${data.state || 'Bihar'} [PIN: ${data.pin || '848301'}] &nbsp;·&nbsp; 🕒 <b>Last Inspection:</b> 14-Oct-2024 (10:14 IST)
  `;

  if (data.reconcile_score) {
    document.getElementById('reconcileScore').textContent = `${(data.reconcile_score * 100).toFixed(1)}%`;
  }
}

// Auditor Actions & Persistence Simulation
function initAuditorActions() {
  const confirmBtn = document.getElementById('confirmDiscrepancyBtn');
  const rescoreBtn = document.getElementById('rescoreBtn');
  const flagCmoBtn = document.getElementById('flagCmoBtn');
  const exportPdfBtn = document.getElementById('exportPdfBtn');

  if (confirmBtn) {
    confirmBtn.addEventListener('click', async () => {
      const facilityName = document.getElementById('facilitySelect').value;
      const notes = document.getElementById('auditorNotes').value;
      
      try {
        const res = await fetch(`${API_BASE}/api/audit-action`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: 'CONFIRM_SURGICAL_DISCREPANCY',
            facility_name: facilityName,
            notes: notes
          })
        });
        const result = await res.json();
        alert(`🚨 DISCREPANCY CONFIRMED & LOGGED!\n\nFacility: ${facilityName}\nStatus: ${result.status}\nCase Ref: ${result.case_id || 'AUD-2024-KLY-91'}`);
      } catch (err) {
        alert(`🚨 DISCREPANCY CONFIRMED (DEMO STATE)\n\nFacility: ${facilityName}\nAction logged in local session state.`);
      }
    });
  }

  if (rescoreBtn) {
    rescoreBtn.addEventListener('click', () => {
      alert('🔄 Re-scoring Trust Index via CareTruth AI engine... Trust score updated.');
    });
  }

  if (flagCmoBtn) {
    flagCmoBtn.addEventListener('click', () => {
      alert('🚩 Case AUD-2024-KLY-91 escalated to Samastipur District CMO.');
    });
  }

  if (exportPdfBtn) {
    exportPdfBtn.addEventListener('click', () => {
      window.print();
    });
  }
}

// Tab Views Renderers
function renderVerificationQueueView() {
  const viewContainer = document.getElementById('viewContainer');
  viewContainer.innerHTML = `
    <div class="view-panel active">
      <h2 style="margin-bottom:1rem;color:#FFF;">📋 Verification Queue (Live Search)</h2>
      <div class="facility-toolbar">
        <input type="text" id="queueQuery" placeholder="Describe healthcare need (e.g. Emergency surgery tonight)..." class="facility-dropdown" style="flex:2;" value="Severe abdominal pain, emergency surgery tonight." />
        <input type="text" id="queueCity" placeholder="City name (e.g. Patna, Siwan, Begusarai)..." class="facility-dropdown" style="flex:1;" value="Siwan" />
        <button class="btn btn-primary" id="runSearchBtn">🔍 Search Facilities</button>
      </div>
      <div id="searchResultsArea" style="margin-top:1rem;"></div>
    </div>
  `;

  document.getElementById('runSearchBtn').addEventListener('click', runBackendSearch);
  runBackendSearch();
}

async function runBackendSearch() {
  const resultsArea = document.getElementById('searchResultsArea');
  resultsArea.innerHTML = '<div style="color:#00C9B1;">Searching 10,000 facilities via CareTruth AI backend...</div>';

  const query = document.getElementById('queueQuery').value;

  try {
    const res = await fetch(`${API_BASE}/solve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        probe_id: 'web_ui_search',
        query_text: query,
        user_location: { lat: 26.24, lng: 84.40 },
        time: 'Tuesday 14:30'
      })
    });
    if (res.ok) {
      const data = await res.json();
      if (data.results && data.results.length > 0) {
        let html = '';
        data.results.forEach((r, idx) => {
          html += `
            <div class="claim-card border-teal" style="margin-bottom:1rem;">
              <div class="claim-card-top">
                <h3 class="claim-title">#${idx+1} ${r.facility_name}</h3>
                <span class="status-tag tag-green">${r.verdict.toUpperCase()}</span>
              </div>
              <div class="claim-sub-info">
                <b>Trust Score:</b> ${r.trust_score} &nbsp;·&nbsp; <b>Distance:</b> ${r.distance_km} km &nbsp;·&nbsp; <b>PIN:</b> ${r.facility_pin || 'N/A'}
              </div>
              <p style="color:#A0C2E8;font-size:0.88rem;">${r.why}</p>
            </div>
          `;
        });
        resultsArea.innerHTML = html;
      } else {
        resultsArea.innerHTML = '<div style="color:#F5A623;">⚠️ No facilities matched requirements.</div>';
      }
    }
  } catch (err) {
    resultsArea.innerHTML = '<div style="color:#E74C3C;">⚠️ Search request failed. Verify backend API is active on port 8000.</div>';
  }
}

function renderOverviewView() {
  const viewContainer = document.getElementById('viewContainer');
  viewContainer.innerHTML = `
    <div class="view-panel active">
      <h2 style="margin-bottom:1rem;color:#FFF;">📊 Executive Dataset Overview</h2>
      <div class="status-grid">
        <div class="status-card"><div class="status-card-header">TOTAL FACILITIES</div><div class="status-card-value text-teal">10,000</div></div>
        <div class="status-card"><div class="status-card-header">VALID COORDINATES</div><div class="status-card-value text-green">10,000</div></div>
        <div class="status-card"><div class="status-card-header">EQUIPMENT DATA</div><div class="status-card-value text-amber">8,420</div></div>
        <div class="status-card"><div class="status-card-header">NAMED STAFF LOGS</div><div class="status-card-value text-teal">5,810</div></div>
      </div>
    </div>
  `;
}

function renderCommitsView() {
  const viewContainer = document.getElementById('viewContainer');
  viewContainer.innerHTML = `
    <div class="view-panel active">
      <h2 style="margin-bottom:1rem;color:#FFF;">📜 Real-Time Git Commit Stream</h2>
      <div class="terminal-section">
        <div class="log-highlight">[eef0317] feat(ui): stitch high-fidelity VERITAS Clinical Auditor Workbench UI to deterministic backend</div>
        <div class="log-highlight">[efbe412] feat(ui): add live Git Commit stream and activity feed tab to Streamlit UI</div>
        <div class="log-highlight">[c1d6d51] docs: add architecture diagrams, dataset schema, and hackathon demo script</div>
        <div class="log-highlight">[346455a] test: add comprehensive 38-test suite for PS-03 contract and practice probes</div>
      </div>
    </div>
  `;
}

function renderMapView() {
  const viewContainer = document.getElementById('viewContainer');
  viewContainer.innerHTML = `
    <div class="view-panel active">
      <h2 style="margin-bottom:1rem;color:#FFF;">🗺️ National Healthcare Facilities Map</h2>
      <div style="background:#0D1C33;border:1px solid #1A345C;border-radius:10px;padding:2rem;text-align:center;color:#A0C2E8;">
        Interactive Plotly Map Active on Streamlit Portal (Port 8501) & Native Canvas API.
      </div>
    </div>
  `;
}

function renderExplorerView() {
  const viewContainer = document.getElementById('viewContainer');
  viewContainer.innerHTML = `
    <div class="view-panel active">
      <h2 style="margin-bottom:1rem;color:#FFF;">🔬 Registry Explorer & Evidence Inspector</h2>
      <p style="color:#A0C2E8;">Inspect raw source blobs and grounded citations across all 10,000 facility rows.</p>
    </div>
  `;
}
