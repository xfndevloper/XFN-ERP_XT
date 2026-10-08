let allWorkers = [];
let allSites = [];
let allMaterials = [];
let allVendors = [];

document.addEventListener('DOMContentLoaded', () => {
  initClock();
  setupTabs();
  loadAllData();
  calcPOTotal();

  // Set default dates for payroll
  const now = new Date();
  const firstDay = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
  const today = now.toISOString().split('T')[0];
  document.getElementById('payrollFromDate').value = firstDay;
  document.getElementById('payrollToDate').value = today;

  // Poll dashboard stream every 10s
  setInterval(() => {
    const activeTab = document.querySelector('.nav-tab.active')?.dataset.tab;
    if (activeTab === 'dashboard') loadDashboard();
  }, 10000);
});

function initClock() {
  const clockEl = document.getElementById('liveClock');
  const update = () => {
    const d = new Date();
    clockEl.innerText = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };
  update();
  setInterval(update, 1000);
}

function setupTabs() {
  const tabs = document.querySelectorAll('.nav-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const target = document.getElementById(`tab-${tab.dataset.tab}`);
      if (target) target.classList.add('active');

      if (tab.dataset.tab === 'workers') loadWorkers();
      if (tab.dataset.tab === 'sites') loadSites();
      if (tab.dataset.tab === 'inventory') loadInventory();
      if (tab.dataset.tab === 'pos') loadPOs();
      if (tab.dataset.tab === 'payroll') loadPayroll();
      if (tab.dataset.tab === 'dashboard') loadDashboard();
    });
  });
}

async function loadAllData() {
  await Promise.all([loadDashboard(), loadSites(), loadInventory(), loadVendors()]);
  loadWorkers();
}

function showToast(msg, isSuccess = true) {
  const t = document.getElementById('toast');
  t.innerText = msg;
  t.style.borderLeftColor = isSuccess ? '#10b981' : '#ef4444';
  t.style.display = 'block';
  setTimeout(() => { t.style.display = 'none'; }, 4000);
}

// 1. Dashboard
async function loadDashboard() {
  try {
    const res = await fetch('/api/dashboard');
    const data = await res.json();
    if (!data.success) return;

    const m = data.metrics;
    document.getElementById('kpiTotalWorkers').innerText = m.total_workers;
    document.getElementById('kpiCheckedInNow').innerText = m.checked_in_now;
    document.getElementById('kpiActiveSites').innerText = m.active_sites;
    document.getElementById('kpiLowStock').innerText = m.low_stock_count;
    document.getElementById('kpiTodayWages').innerText = `₹${m.today_wages.toLocaleString('en-IN')}`;
    document.getElementById('kpiTotalPOs').innerText = `₹${m.total_pos.toLocaleString('en-IN')}`;

    const tbody = document.getElementById('dashboardLogsBody');
    if (!data.recent_logs.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:#94a3b8;">No attendance punches recorded yet today.</td></tr>';
      return;
    }

    tbody.innerHTML = data.recent_logs.map(log => `
      <tr>
        <td><strong>${log.worker_name}</strong></td>
        <td><span class="badge badge-trade">${log.trade}</span></td>
        <td>${log.site_name || 'Site Alpha'}</td>
        <td>${log.check_in ? log.check_in.split(' ')[1] : '--'}</td>
        <td>${log.check_out ? log.check_out.split(' ')[1] : '<span style="color:#10b981; font-weight:600;">Active</span>'}</td>
        <td><span class="badge ${log.check_out ? 'badge-out' : 'badge-in'}">${log.check_out ? 'Completed' : 'Working'}</span></td>
        <td><strong>₹${(log.daily_wage_earned || 0).toLocaleString('en-IN')}</strong></td>
      </tr>
    `).join('');
  } catch (err) {
    console.error(err);
  }
}

// 2. Workers & Kiosk
async function loadWorkers() {
  try {
    const res = await fetch('/api/workers');
    const data = await res.json();
    if (!data.success) return;
    allWorkers = data.workers;
    renderWorkers(allWorkers);
  } catch (err) {
    console.error(err);
  }
}

function renderWorkers(workers) {
  const container = document.getElementById('workersContainer');
  if (!workers.length) {
    container.innerHTML = '<div style="padding:20px; color:#94a3b8;">No matching workers found.</div>';
    return;
  }

  container.innerHTML = workers.map(w => {
    const isChecked = w.is_checked_in == 1;
    return `
      <div class="worker-card" style="border-top: 4px solid ${isChecked ? '#10b981' : '#cbd5e1'};">
        <div class="worker-card-header">
          <div>
            <div class="worker-name">${w.name}</div>
            <div class="worker-code">${w.emp_code} • ${w.phone || 'No Phone'}</div>
          </div>
          <span class="badge ${isChecked ? 'badge-in' : 'badge-out'}">${isChecked ? 'ON SITE' : 'OFF DUTY'}</span>
        </div>
        <div class="worker-details">
          <div><strong>Trade:</strong> <span class="badge badge-trade">${w.trade}</span></div>
          <div><strong>Daily Wage:</strong> ₹${w.daily_wage}/day (OT: ₹${w.overtime_rate}/hr)</div>
          <div><strong>Current Site:</strong> ${w.site_name || 'General Construction'}</div>
        </div>
        <button class="worker-punch-btn ${isChecked ? 'btn-danger' : 'btn-success'}" onclick="punchKiosk(${w.id})">
          ${isChecked ? '🚪 Check Out (Punch Out)' : '📲 Check In (Punch In)'}
        </button>
      </div>
    `;
  }).join('');
}

function filterWorkers() {
  const search = document.getElementById('workerSearchInput').value.toLowerCase();
  const trade = document.getElementById('workerTradeFilter').value;
  const siteId = document.getElementById('headerSiteFilter').value;

  const filtered = allWorkers.filter(w => {
    const matchSearch = w.name.toLowerCase().includes(search) || w.emp_code.toLowerCase().includes(search) || (w.phone && w.phone.includes(search));
    const matchTrade = !trade || w.trade === trade;
    const matchSite = !siteId || String(w.site_id) === String(siteId);
    return matchSearch && matchTrade && matchSite;
  });
  renderWorkers(filtered);
}

async function punchKiosk(workerId) {
  const w = allWorkers.find(x => x.id === workerId);
  const siteId = document.getElementById('headerSiteFilter').value || (w ? w.site_id : 1);

  try {
    const res = await fetch('/api/kiosk/punch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ worker_id: workerId, site_id: siteId })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, true);
      await loadWorkers();
      loadDashboard();
    } else {
      showToast(data.message, false);
    }
  } catch (err) {
    showToast('Failed to connect to server', false);
  }
}

// 3. Sites
async function loadSites() {
  try {
    const res = await fetch('/api/sites');
    const data = await res.json();
    if (!data.success) return;
    allSites = data.sites;

    const tbody = document.getElementById('sitesTableBody');
    tbody.innerHTML = allSites.map(s => `
      <tr>
        <td><strong>${s.code}</strong></td>
        <td><strong>${s.name}</strong></td>
        <td>${s.location}</td>
        <td>${s.manager_name}</td>
        <td><span class="badge badge-trade">${s.worker_count} Workers</span></td>
        <td><span class="badge badge-in">${s.present_count} Present</span></td>
        <td><strong>₹${(s.budget || 0).toLocaleString('en-IN')}</strong></td>
        <td><span class="badge badge-in">${s.status}</span></td>
      </tr>
    `).join('');

    // Update site dropdowns
    const siteSelects = ['headerSiteFilter', 'newWorkerSite', 'stockMoveSite', 'poSite'];
    siteSelects.forEach(selId => {
      const el = document.getElementById(selId);
      if (!el) return;
      const cur = el.value;
      if (selId === 'headerSiteFilter') {
        el.innerHTML = '<option value="">🌐 All Construction Sites</option>' + allSites.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
      } else {
        el.innerHTML = allSites.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
      }
      el.value = cur;
    });
  } catch (err) {
    console.error(err);
  }
}

// 4. Inventory & Movements
async function loadInventory() {
  try {
    const res = await fetch('/api/inventory');
    const data = await res.json();
    if (!data.success) return;
    allMaterials = data.items;

    const tbody = document.getElementById('inventoryTableBody');
    tbody.innerHTML = allMaterials.map(m => {
      const isLow = m.current_stock <= m.min_reorder_level;
      return `
        <tr>
          <td><strong>${m.item_code}</strong></td>
          <td><strong>${m.name}</strong></td>
          <td><span class="badge badge-trade">${m.category}</span></td>
          <td><strong>${m.current_stock} ${m.unit}</strong></td>
          <td>${m.min_reorder_level} ${m.unit}</td>
          <td>₹${(m.standard_cost || 0).toLocaleString('en-IN')}</td>
          <td><span class="badge ${isLow ? 'badge-stock-low' : 'badge-in'}">${isLow ? '⚠️ LOW STOCK' : 'IN STOCK'}</span></td>
        </tr>
      `;
    }).join('');

    // Stock move item selector
    const sel = document.getElementById('stockMoveItem');
    if (sel) {
      sel.innerHTML = allMaterials.map(m => `<option value="${m.id}">${m.name} (${m.unit}) - Current: ${m.current_stock}</option>`).join('');
    }

    // Load recent movements
    const mRes = await fetch('/api/stock-movements');
    const mData = await mRes.json();
    if (mData.success) {
      const mBody = document.getElementById('movementsTableBody');
      mBody.innerHTML = mData.movements.map(mv => `
        <tr>
          <td>${mv.date}</td>
          <td><span class="badge ${mv.movement_type === 'INWARD' ? 'badge-in' : 'badge-trade'}">${mv.movement_type}</span></td>
          <td><strong>${mv.item_name}</strong></td>
          <td><strong>${mv.quantity} ${mv.unit}</strong></td>
          <td>${mv.site_name || 'Central Warehouse'}</td>
          <td>${mv.handled_by || 'Store'}</td>
          <td>${mv.reference_no || '-'}</td>
        </tr>
      `).join('');
    }
  } catch (err) {
    console.error(err);
  }
}

// 5. Purchase Orders
async function loadVendors() {
  try {
    const res = await fetch('/api/vendors');
    const data = await res.json();
    if (!data.success) return;
    allVendors = data.vendors;
    const vSel = document.getElementById('poVendor');
    if (vSel) {
      vSel.innerHTML = allVendors.map(v => `<option value="${v.id}">${v.name} (GSTIN: ${v.gstin})</option>`).join('');
    }
  } catch (err) {
    console.error(err);
  }
}

async function loadPOs() {
  try {
    const res = await fetch('/api/purchase-orders');
    const data = await res.json();
    if (!data.success) return;

    const tbody = document.getElementById('poTableBody');
    tbody.innerHTML = data.purchase_orders.map(po => `
      <tr>
        <td><strong>${po.po_number}</strong></td>
        <td>${po.date}</td>
        <td><strong>${po.vendor_name}</strong></td>
        <td>${po.site_name || 'Headquarters'}</td>
        <td>₹${(po.subtotal || 0).toLocaleString('en-IN')}</td>
        <td>${po.gst_rate}%</td>
        <td><strong style="color:var(--primary);">₹${(po.grand_total || 0).toLocaleString('en-IN')}</strong></td>
        <td><span class="badge badge-in">${po.status}</span></td>
      </tr>
    `).join('');
  } catch (err) {
    console.error(err);
  }
}

function calcPOTotal() {
  const qty = parseFloat(document.getElementById('poQty')?.value || 0);
  const rate = parseFloat(document.getElementById('poRate')?.value || 0);
  const gst = parseFloat(document.getElementById('poGSTRate')?.value || 18);

  const sub = qty * rate;
  const tax = sub * (gst / 100.0);
  const total = sub + tax;

  const subEl = document.getElementById('poSubtotalLabel');
  const gstEl = document.getElementById('poGSTLabel');
  const totEl = document.getElementById('poGrandTotalLabel');

  if (subEl) subEl.innerText = `₹${sub.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
  if (gstEl) gstEl.innerText = `₹${tax.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
  if (totEl) totEl.innerText = `₹${total.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
}

// 6. Payroll
async function loadPayroll() {
  const from = document.getElementById('payrollFromDate').value;
  const to = document.getElementById('payrollToDate').value;

  try {
    const res = await fetch(`/api/payroll?from=${from}&to=${to}`);
    const data = await res.json();
    if (!data.success) return;

    const tbody = document.getElementById('payrollTableBody');
    tbody.innerHTML = data.payroll.map(p => `
      <tr>
        <td><strong>${p.emp_code}</strong></td>
        <td><strong>${p.name}</strong></td>
        <td><span class="badge badge-trade">${p.trade}</span></td>
        <td>${p.site_name || 'General'}</td>
        <td>₹${p.daily_wage}</td>
        <td><strong>${p.days_present} Days</strong></td>
        <td>${p.total_hours} hrs</td>
        <td>${p.total_ot_hours} hrs</td>
        <td><strong style="color:var(--success); font-size:0.95rem;">₹${(p.total_wage_earned || 0).toLocaleString('en-IN')}</strong></td>
      </tr>
    `).join('');
  } catch (err) {
    console.error(err);
  }
}

function exportPayrollCSV() {
  const from = document.getElementById('payrollFromDate').value;
  const to = document.getElementById('payrollToDate').value;
  window.open(`/api/export-payroll-csv?from=${from}&to=${to}`, '_blank');
}

// Modals
function openModal(id) { document.getElementById(id).classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); }

function openAddWorkerModal() { openModal('modalAddWorker'); }
async function submitAddWorker(e) {
  e.preventDefault();
  const payload = {
    name: document.getElementById('newWorkerName').value,
    trade: document.getElementById('newWorkerTrade').value,
    daily_wage: document.getElementById('newWorkerWage').value,
    overtime_rate: document.getElementById('newWorkerOT').value,
    site_id: document.getElementById('newWorkerSite').value,
    phone: document.getElementById('newWorkerPhone').value,
    pin: document.getElementById('newWorkerPIN').value
  };

  const res = await fetch('/api/workers/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (data.success) {
    showToast(data.message, true);
    closeModal('modalAddWorker');
    loadWorkers();
    loadDashboard();
  }
}

function openStockModal(type) {
  document.getElementById('stockMoveType').value = type;
  document.getElementById('stockMoveTitle').innerText = type === 'INWARD' ? '📥 Material Inward (MRN)' : '📤 Site Issue Note (Outward)';
  openModal('modalStockMove');
}

async function submitStockMove(e) {
  e.preventDefault();
  const payload = {
    movement_type: document.getElementById('stockMoveType').value,
    item_id: document.getElementById('stockMoveItem').value,
    site_id: document.getElementById('stockMoveSite').value,
    quantity: document.getElementById('stockMoveQty').value,
    unit_rate: document.getElementById('stockMoveRate').value,
    reference_no: document.getElementById('stockMoveRef').value
  };

  const res = await fetch('/api/stock/movement', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (data.success) {
    showToast(data.message, true);
    closeModal('modalStockMove');
    loadInventory();
    loadDashboard();
  } else {
    showToast(data.message, false);
  }
}

function openCreatePOModal() { openModal('modalCreatePO'); }
async function submitCreatePO(e) {
  e.preventDefault();
  const payload = {
    vendor_id: document.getElementById('poVendor').value,
    site_id: document.getElementById('poSite').value,
    gst_rate: document.getElementById('poGSTRate').value,
    items: [{
      description: document.getElementById('poItemDesc').value,
      quantity: document.getElementById('poQty').value,
      rate: document.getElementById('poRate').value
    }]
  };

  const res = await fetch('/api/purchase-orders/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (data.success) {
    showToast(data.message, true);
    closeModal('modalCreatePO');
    loadPOs();
    loadDashboard();
  }
}
