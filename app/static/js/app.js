'use strict';

// Global 401 interceptor
const _origFetch = window.fetch;
window.fetch = async function(...args) {
  const res = await _origFetch.apply(this, args);
  if (res.status === 401 && !window.location.pathname.startsWith('/login')) {
    window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname + window.location.search);
  }
  return res;
};

const isDemoMode = window.location.search.includes('demo=1');
const apiParam = (url) => isDemoMode ? (url.includes('?') ? `${url}&demo=1` : `${url}?demo=1`) : url;

let allProfiles = [];
let savedProxies = [];
let savedFolders = [];
let activeFilter = 'all';
let activeFolderFilter = 'all';

const PRESET_COLORS = [
  '#2563eb', // Blue
  '#059669', // Emerald
  '#d97706', // Amber
  '#7c3aed', // Purple
  '#db2777', // Pink
  '#dc2626', // Red
  '#0891b2', // Cyan
  '#64748b', // Slate
];

// Toast Notification
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 200);
  }, 4000);
}

// Formatters
function esc(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatDiskSize(mb) {
  if (mb === null || mb === undefined || isNaN(mb)) return '0.0 MB';
  const num = parseFloat(mb);
  if (num >= 1024) {
    return `${(num / 1024).toFixed(1)} GB`;
  }
  return `${num.toFixed(1)} MB`;
}

// Telemetry Poller
async function fetchTelemetry() {
  try {
    const res = await fetch(apiParam('/api/telemetry'));
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById('m-total-profiles').textContent = data.total_profiles;
    document.getElementById('m-running-profiles').textContent = data.running_profiles;
    const ramUsed = (data.ram_used_gb !== undefined ? data.ram_used_gb : data.memory_used_gb) ?? '3.8';
    const ramTotal = (data.ram_total_gb !== undefined ? data.ram_total_gb : data.memory_total_gb) ?? '24.0';
    const storageMb = (data.storage_profiles_mb !== undefined ? data.storage_profiles_mb : data.profiles_storage_mb) ?? '166.5';
    document.getElementById('m-ram').textContent = `${ramUsed} / ${ramTotal} GB`;
    document.getElementById('m-disk').textContent = `${storageMb} MB`;

    document.getElementById('badge-count-all').textContent = data.total_profiles;
    document.getElementById('badge-count-running').textContent = data.running_profiles;
    document.getElementById('badge-count-stopped').textContent = data.total_profiles - data.running_profiles;

    const pAll = document.getElementById('pill-count-all');
    if (pAll) pAll.textContent = data.total_profiles;
    const pRun = document.getElementById('pill-count-running');
    if (pRun) pRun.textContent = data.running_profiles;
    const pStop = document.getElementById('pill-count-stopped');
    if (pStop) pStop.textContent = data.total_profiles - data.running_profiles;
  } catch (err) {
    // silent background telemetry poll
  }
}

// Folders Management
async function fetchFolders() {
  try {
    const res = await fetch(apiParam('/api/folders'));
    if (res.ok) {
      savedFolders = await res.json();
      renderSidebarFolders();
      populateFolderSelects();
    }
  } catch (err) {
    savedFolders = [];
  }
}

function renderSidebarFolders() {
  const container = document.getElementById('sidebar-folders-list');
  if (!container) return;

  container.innerHTML = savedFolders.map(f => {
    const isActive = activeFolderFilter === f.id;
    const isDefault = f.id === 'default';

    return `
      <div class="folder-nav-item ${isActive ? 'active' : ''}" data-folder-id="${esc(f.id)}">
        <div class="folder-nav-left" title="${esc(f.description || f.name)}">
          <span class="folder-color-dot" style="background:${f.color || '#64748b'};"></span>
          <span>${esc(f.name)}</span>
        </div>
        <div style="display:flex; align-items:center; gap:6px;">
          <span class="nav-count">${f.total_profiles || 0}</span>
          ${!isDefault ? `
            <div class="folder-nav-actions">
              <button class="folder-action-btn" onclick="event.stopPropagation(); openEditFolderModal('${esc(f.id)}')" title="Edit Folder">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
              </button>
              <button class="folder-action-btn" onclick="event.stopPropagation(); confirmDeleteFolder('${esc(f.id)}')" title="Delete Folder">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
              </button>
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }).join('');

  // Bind clicks
  container.querySelectorAll('.folder-nav-item').forEach(el => {
    el.addEventListener('click', () => {
      const fid = el.dataset.folderId;
      if (activeFolderFilter === fid) {
        activeFolderFilter = 'all'; // toggle off to all
      } else {
        activeFolderFilter = fid;
      }
      syncFolderFilterUI();
      renderProfilesTable();
    });
  });
}

function syncFolderFilterUI() {
  // Sync sidebar active class
  document.querySelectorAll('.folder-nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.folderId === activeFolderFilter);
  });
  // Sync folder dropdown
  const sel = document.getElementById('folder-filter-select');
  if (sel) sel.value = activeFolderFilter;
}

function populateFolderSelects() {
  const filterSel = document.getElementById('folder-filter-select');
  if (filterSel) {
    const cur = filterSel.value || 'all';
    filterSel.innerHTML = `
      <option value="all">All Folders</option>
      ${savedFolders.map(f => `<option value="${esc(f.id)}">${esc(f.name)} (${f.total_profiles || 0})</option>`).join('')}
    `;
    filterSel.value = activeFolderFilter;
  }

  const createSel = document.getElementById('create-folder-select');
  if (createSel) {
    const cur = createSel.value;
    createSel.innerHTML = savedFolders.map(f => `
      <option value="${esc(f.id)}">${esc(f.name)}</option>
    `).join('');
    if (activeFolderFilter !== 'all') {
      createSel.value = activeFolderFilter;
    } else if (cur) {
      createSel.value = cur;
    } else {
      createSel.value = 'default';
    }
  }

  const editSel = document.getElementById('edit-folder-select');
  if (editSel) {
    const cur = editSel.value;
    editSel.innerHTML = savedFolders.map(f => `
      <option value="${esc(f.id)}">${esc(f.name)}</option>
    `).join('');
    if (cur) editSel.value = cur;
  }

  const deleteTargetSel = document.getElementById('folder-delete-target-select');
  if (deleteTargetSel) {
    deleteTargetSel.innerHTML = savedFolders
      .filter(f => f.id !== currentDeleteFolderId)
      .map(f => `<option value="${esc(f.id)}">${esc(f.name)}</option>`)
      .join('');
  }
}

// Proxies Store
async function fetchProxies() {
  try {
    const res = await fetch(apiParam('/api/proxies'));
    if (res.ok) {
      savedProxies = await res.json();
      populateProxySelects();
    }
  } catch (err) {
    savedProxies = [];
  }
}

function populateProxySelects() {
  const selects = ['create-proxy-select', 'edit-proxy-select'];
  selects.forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = `
      <option value="">Direct (No Proxy)</option>
      ${savedProxies.map(p => `<option value="${esc(p.name)}">${esc(p.name)} (${esc(p.url)})</option>`).join('')}
      <option value="__custom__">Custom URL...</option>
    `;
    sel.value = current || '';
  });
}

// Profiles List
async function fetchProfiles() {
  try {
    const res = await fetch(apiParam('/api/profiles'));
    if (!res.ok) throw new Error('Failed to load profiles');
    allProfiles = await res.json();
    renderProfilesTable();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function renderProfilesTable() {
  const tbody = document.getElementById('profiles-tbody');
  const cardsFeed = document.getElementById('profiles-cards-feed');
  const emptyState = document.getElementById('empty-state');
  const query = (document.getElementById('search-input')?.value || '').toLowerCase();

  let filtered = allProfiles.filter(p => {
    // Status filter
    if (activeFilter === 'running' && p.status !== 'running') return false;
    if (activeFilter === 'stopped' && p.status === 'running') return false;
    // Folder filter
    if (activeFolderFilter !== 'all' && (p.folder || 'default') !== activeFolderFilter) return false;
    // Search query
    if (query) {
      const matchName = p.name.toLowerCase().includes(query);
      const matchNote = (p.note || '').toLowerCase().includes(query);
      const matchProxy = (p.proxy || '').toLowerCase().includes(query);
      const matchFolder = (p.folder_name || '').toLowerCase().includes(query);
      return matchName || matchNote || matchProxy || matchFolder;
    }
    return true;
  });

  if (filtered.length === 0) {
    if (tbody) tbody.innerHTML = '';
    if (cardsFeed) cardsFeed.innerHTML = '';
    emptyState.style.display = 'flex';
    return;
  }
  emptyState.style.display = 'none';

  // Render Desktop Table
  if (tbody) {
    tbody.innerHTML = filtered.map(p => {
      const isRunning = p.status === 'running';
      const m = p.machine || {};
      const chips = [
        m.cpu_cores ? `${m.cpu_cores} Cores` : null,
        m.screen_resolution || null,
        m.timezone ? m.timezone.split('/').pop().replace(/_/g, ' ') : null,
      ].filter(Boolean);

      // Parse proxy protocol and host cleanly
      let proxyProto = 'Direct';
      let proxyHost = 'Local Loopback';
      if (p.proxy) {
        try {
          const u = new URL(p.proxy);
          proxyProto = u.protocol.replace(':', '').toUpperCase();
          proxyHost = u.host;
        } catch {
          const parts = p.proxy.split('://');
          proxyProto = parts[0].toUpperCase();
          proxyHost = parts[1] || p.proxy;
        }
      }

      return `
        <tr data-name="${esc(p.name)}" class="${isRunning ? 'row-running' : ''}">
          <!-- 1. Profile & Identity -->
          <td>
            <div class="profile-cell-identity">
              <div class="profile-avatar ${isRunning ? 'is-running' : ''}">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                  <line x1="8" y1="21" x2="16" y2="21"></line>
                  <line x1="12" y1="17" x2="12" y2="21"></line>
                </svg>
                ${isRunning ? '<span class="avatar-pulse-dot"></span>' : ''}
              </div>
              <div class="profile-meta">
                <div class="profile-name-row">
                  <a href="${isRunning ? `/viewer/${encodeURIComponent(p.name)}` : 'javascript:void(0)'}" 
                     class="profile-name-link ${isRunning ? 'clickable' : ''}" 
                     ${isRunning ? 'target="_blank" title="Open Interactive Stream"' : `onclick="openEditModal('${esc(p.name)}')"`}>
                    ${esc(p.name)}
                  </a>
                  ${p.start_url ? `
                    <a href="${esc(p.start_url)}" target="_blank" class="profile-ext-link" title="Target: ${esc(p.start_url)}">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                    </a>
                  ` : ''}
                </div>
                ${p.note ? `<div class="profile-desc">${esc(p.note)}</div>` : ''}
                <div class="profile-spec-chips">
                  ${chips.map(c => `<span class="spec-pill">${esc(c)}</span>`).join('')}
                </div>
              </div>
            </div>
          </td>

          <!-- 2. Folder -->
          <td>
            <span class="chip-folder">
              <span class="chip-folder-dot" style="background:${p.folder_color || '#64748b'};"></span>
              ${esc(p.folder_name || 'General')}
            </span>
          </td>

          <!-- 3. Status & Ports -->
          <td>
            <div class="status-cell-wrap">
              <span class="badge ${isRunning ? 'badge-running' : 'badge-stopped'}">
                <span class="badge-dot ${isRunning ? 'ping' : ''}"></span>
                ${isRunning ? 'ACTIVE' : 'OFFLINE'}
              </span>
              ${isRunning ? `
                <div class="port-chips-group">
                  <span class="port-chip vnc" title="VNC Stream: Port ${p.vnc_port || '-'}">VNC :${p.vnc_port || '-'}</span>
                  <span class="port-chip cdp" title="CDP DevTools: Port ${p.cdp_port || '-'}">CDP :${p.cdp_port || '-'}</span>
                </div>
              ` : '<span class="status-idle-text">0% CPU / 0 MB</span>'}
            </div>
          </td>

          <!-- 4. Network / Proxy -->
          <td>
            ${p.proxy ? `
              <div class="proxy-badge-wrap" title="${esc(p.proxy)}">
                <span class="proxy-protocol-tag">${esc(proxyProto)}</span>
                <span class="proxy-host-text">${esc(proxyHost)}</span>
              </div>
            ` : `
              <div class="proxy-direct-wrap">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                <span>Direct Route</span>
              </div>
            `}
          </td>

          <!-- 5. Disk Usage -->
          <td>
            <div class="disk-usage-cell">
              <span class="disk-size-num">${formatDiskSize(p.size_mb)}</span>
              <span class="disk-sub-date">${p.created_at ? p.created_at.split(' ')[0] : 'Active'}</span>
            </div>
          </td>

          <!-- 6. Quick Actions -->
          <td style="text-align: right;">
            <div class="row-actions-group">
              ${isRunning ? `
                <button class="btn btn-primary btn-sm btn-action-main" onclick="openViewer('${esc(p.name)}')" title="Open HTML5 Interactive Stream">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>
                  <span>Screen</span>
                </button>
                <button class="btn btn-danger-soft btn-sm btn-icon-action" onclick="stopProfile('${esc(p.name)}')" title="Stop Active Container">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="1"></rect></svg>
                </button>
              ` : `
                <button class="btn btn-success btn-sm btn-action-main" onclick="startProfile('${esc(p.name)}')" title="Launch Profile Container">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 4 18 12 6 20 6 4"></polygon></svg>
                  <span>Launch</span>
                </button>
              `}

              <div class="action-icon-toolbar">
                <button class="btn-icon-tbl" onclick="openEditModal('${esc(p.name)}')" title="Edit Profile Settings">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                </button>
                <button class="btn-icon-tbl" onclick="exportProfile('${esc(p.name)}')" title="Download Compressed ZIP Archive">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                </button>
                <button class="btn-icon-tbl btn-icon-danger-tbl" onclick="confirmDelete('${esc(p.name)}')" title="Delete Profile and Container Storage">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </button>
              </div>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  }

  // Render Mobile Cards Feed
  if (cardsFeed) {
    cardsFeed.innerHTML = filtered.map(p => {
      const isRunning = p.status === 'running';
      const m = p.machine || {};
      const chips = [
        m.cpu_cores ? `${m.cpu_cores} Cores` : null,
        m.screen_resolution || null,
        m.timezone ? m.timezone.split('/').pop().replace(/_/g, ' ') : null,
        m.language || null,
      ].filter(Boolean);

      return `
        <div class="profile-feed-card" data-name="${esc(p.name)}">
          <div class="profile-feed-header">
            <div>
              <div class="profile-feed-title">${esc(p.name)}</div>
              ${p.note ? `<div class="profile-feed-note">${esc(p.note)}</div>` : ''}
              <div style="margin-top:4px;">
                <span class="chip-folder">
                  <span class="chip-folder-dot" style="background:${p.folder_color || '#64748b'};"></span>
                  ${esc(p.folder_name || 'General')}
                </span>
              </div>
            </div>
            <span class="badge ${isRunning ? 'badge-running' : 'badge-stopped'}">
              <span class="badge-dot"></span>
              ${isRunning ? 'Running' : 'Stopped'}
            </span>
          </div>

          ${chips.length ? `
            <div class="profile-feed-chips">
              ${chips.map(c => `<span class="chip">${esc(c)}</span>`).join('')}
            </div>
          ` : ''}

          <div class="profile-feed-meta-grid">
            <div class="meta-grid-item">
              <span class="meta-grid-label">Proxy</span>
              <span class="meta-grid-val">${p.proxy ? esc(p.proxy) : 'Direct'}</span>
            </div>
            <div class="meta-grid-item">
              <span class="meta-grid-label">Storage</span>
              <span class="meta-grid-val">${formatDiskSize(p.size_mb)}</span>
            </div>
            ${isRunning ? `
              <div class="meta-grid-item">
                <span class="meta-grid-label">VNC Port</span>
                <span class="meta-grid-val" style="color:var(--primary); font-weight:600;">${p.vnc_port || '-'}</span>
              </div>
              <div class="meta-grid-item">
                <span class="meta-grid-label">CDP Debug</span>
                <span class="meta-grid-val" style="color:#0284c7; font-weight:600;">${p.cdp_port || '-'}</span>
              </div>
            ` : ''}
          </div>

          <div class="profile-feed-actions">
            ${isRunning ? `
              <button class="btn btn-secondary" onclick="openViewer('${esc(p.name)}')">View Screen</button>
              <button class="btn btn-danger" onclick="stopProfile('${esc(p.name)}')">Stop</button>
            ` : `
              <button class="btn btn-success" onclick="startProfile('${esc(p.name)}')">Launch</button>
            `}
            <button class="btn btn-secondary" onclick="openEditModal('${esc(p.name)}')">Edit</button>
            <button class="btn btn-secondary" onclick="exportProfile('${esc(p.name)}')">Export</button>
            <button class="btn btn-danger" onclick="confirmDelete('${esc(p.name)}')">Delete</button>
          </div>
        </div>
      `;
    }).join('');
  }
}

// Profile Actions
async function startProfile(name) {
  try {
    showToast(`Starting profile ${name}...`, 'info');
    const res = await fetch(`/api/profiles/${encodeURIComponent(name)}/start`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Start failed');
    showToast(`Profile ${name} started on port ${data.vnc_port}`, 'success');
    await fetchProfiles();
    await fetchTelemetry();
    await fetchFolders();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function stopProfile(name) {
  try {
    const res = await fetch(`/api/profiles/${encodeURIComponent(name)}/stop`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Stop failed');
    showToast(`Profile ${name} stopped`, 'info');
    await fetchProfiles();
    await fetchTelemetry();
    await fetchFolders();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function openViewer(name) {
  window.open(`/viewer/${encodeURIComponent(name)}`, '_blank');
}

function exportProfile(name) {
  window.location.href = `/api/profiles/${encodeURIComponent(name)}/export`;
}

// Modal Helpers
function openModal(id) {
  document.getElementById(id)?.classList.add('active');
}

function closeModal(id) {
  document.getElementById(id)?.classList.remove('active');
}

// Create Profile
const triggerNewProfileModal = () => {
  populateProxySelects();
  populateFolderSelects();
  document.getElementById('create-form').reset();
  document.getElementById('create-proxy-custom').style.display = 'none';
  openModal('modal-create');
};

document.getElementById('btn-new-profile')?.addEventListener('click', triggerNewProfileModal);
document.getElementById('btn-topbar-new')?.addEventListener('click', triggerNewProfileModal);
document.getElementById('btn-mobile-new')?.addEventListener('click', triggerNewProfileModal);

// Import Profile from Topbar
document.getElementById('btn-topbar-import')?.addEventListener('click', () => {
  openModal('modal-import');
});

document.getElementById('create-proxy-select')?.addEventListener('change', (e) => {
  const customInput = document.getElementById('create-proxy-custom');
  customInput.style.display = e.target.value === '__custom__' ? 'block' : 'none';
});

document.getElementById('create-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('create-name').value.trim();
  const folder = document.getElementById('create-folder-select').value || 'default';
  const selectVal = document.getElementById('create-proxy-select').value;
  const customVal = document.getElementById('create-proxy-custom').value.trim();
  const proxy = selectVal === '__custom__' ? customVal : selectVal;
  const startUrl = document.getElementById('create-start-url').value.trim();
  const hostMount = document.getElementById('create-host-mount').value.trim();
  const note = document.getElementById('create-note').value.trim();

  try {
    const res = await fetch('/api/profiles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, folder, proxy, start_url: startUrl, host_mount: hostMount, note }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Creation failed');
    showToast(`Profile "${name}" created successfully`, 'success');
    closeModal('modal-create');
    await fetchProfiles();
    await fetchTelemetry();
    await fetchFolders();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

// Edit Profile
let currentEditName = '';
function openEditModal(name) {
  const p = allProfiles.find(x => x.name === name);
  if (!p) return;
  currentEditName = name;
  document.getElementById('edit-modal-title').textContent = `Edit Profile: ${name}`;
  document.getElementById('edit-start-url').value = p.start_url || '';
  document.getElementById('edit-host-mount').value = p.host_mount || '';
  document.getElementById('edit-note').value = p.note || '';

  populateFolderSelects();
  const folderSel = document.getElementById('edit-folder-select');
  if (folderSel) folderSel.value = p.folder || 'default';

  populateProxySelects();
  const proxySel = document.getElementById('edit-proxy-select');
  const customInput = document.getElementById('edit-proxy-custom');

  const isSaved = savedProxies.some(x => x.name === p.proxy);
  if (isSaved) {
    proxySel.value = p.proxy;
    customInput.style.display = 'none';
  } else if (p.proxy) {
    proxySel.value = '__custom__';
    customInput.value = p.proxy;
    customInput.style.display = 'block';
  } else {
    proxySel.value = '';
    customInput.style.display = 'none';
  }

  openModal('modal-edit');
}

document.getElementById('edit-proxy-select')?.addEventListener('change', (e) => {
  const customInput = document.getElementById('edit-proxy-custom');
  customInput.style.display = e.target.value === '__custom__' ? 'block' : 'none';
});

document.getElementById('edit-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!currentEditName) return;
  const folder = document.getElementById('edit-folder-select').value;
  const selectVal = document.getElementById('edit-proxy-select').value;
  const customVal = document.getElementById('edit-proxy-custom').value.trim();
  const proxy = selectVal === '__custom__' ? customVal : selectVal;
  const startUrl = document.getElementById('edit-start-url').value.trim();
  const hostMount = document.getElementById('edit-host-mount').value.trim();
  const note = document.getElementById('edit-note').value.trim();

  try {
    const res = await fetch(`/api/profiles/${encodeURIComponent(currentEditName)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder, proxy, start_url: startUrl, host_mount: hostMount, note }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Update failed');
    showToast(`Profile "${currentEditName}" updated`, 'success');
    closeModal('modal-edit');
    await fetchProfiles();
    await fetchTelemetry();
    await fetchFolders();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

// Delete Profile
let currentDeleteName = '';
function confirmDelete(name) {
  currentDeleteName = name;
  document.getElementById('delete-msg').textContent = `Are you sure you want to delete "${name}"? All profile cookies and downloads will be removed.`;
  openModal('modal-delete');
}

document.getElementById('btn-confirm-delete')?.addEventListener('click', async () => {
  if (!currentDeleteName) return;
  try {
    const res = await fetch(`/api/profiles/${encodeURIComponent(currentDeleteName)}`, { method: 'DELETE' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Delete failed');
    showToast(`Profile "${currentDeleteName}" deleted`, 'info');
    closeModal('modal-delete');
    await fetchProfiles();
    await fetchTelemetry();
    await fetchFolders();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

// ── Folder CRUD & Modals ───────────────────────────────────────────────────────
function initColorPalettes() {
  const createPalette = document.getElementById('folder-create-palette');
  const editPalette = document.getElementById('folder-edit-palette');

  [createPalette, editPalette].forEach(palette => {
    if (!palette) return;
    palette.innerHTML = PRESET_COLORS.map(c => `
      <div class="color-swatch ${c === '#2563eb' ? 'active' : ''}" style="background:${c};" data-color="${c}"></div>
    `).join('');

    palette.querySelectorAll('.color-swatch').forEach(sw => {
      sw.addEventListener('click', () => {
        palette.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('active'));
        sw.classList.add('active');
        const hiddenInput = palette.parentElement.querySelector('input[type="hidden"]');
        if (hiddenInput) hiddenInput.value = sw.dataset.color;
      });
    });
  });
}

document.getElementById('btn-add-folder')?.addEventListener('click', () => {
  document.getElementById('folder-create-form').reset();
  initColorPalettes();
  openModal('modal-folder-create');
});

document.getElementById('btn-quick-create-folder')?.addEventListener('click', () => {
  document.getElementById('folder-create-form').reset();
  initColorPalettes();
  openModal('modal-folder-create');
});

document.getElementById('folder-create-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('folder-create-name').value.trim();
  const description = document.getElementById('folder-create-desc').value.trim();
  const color = document.getElementById('folder-create-color').value.trim();

  try {
    const res = await fetch('/api/folders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description, color }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to create folder');
    showToast(`Folder "${name}" created`, 'success');
    closeModal('modal-folder-create');
    await fetchFolders();
    activeFolderFilter = data.id;
    syncFolderFilterUI();
    renderProfilesTable();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

let currentEditFolderId = '';
function openEditFolderModal(id) {
  const f = savedFolders.find(x => x.id === id);
  if (!f) return;
  currentEditFolderId = id;
  document.getElementById('folder-edit-id').value = f.id;
  document.getElementById('folder-edit-name').value = f.name;
  document.getElementById('folder-edit-desc').value = f.description || '';
  document.getElementById('folder-edit-color').value = f.color || '#2563eb';

  initColorPalettes();
  const palette = document.getElementById('folder-edit-palette');
  palette?.querySelectorAll('.color-swatch').forEach(sw => {
    sw.classList.toggle('active', sw.dataset.color === f.color);
  });

  openModal('modal-folder-edit');
}

document.getElementById('folder-edit-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!currentEditFolderId) return;
  const name = document.getElementById('folder-edit-name').value.trim();
  const description = document.getElementById('folder-edit-desc').value.trim();
  const color = document.getElementById('folder-edit-color').value.trim();

  try {
    const res = await fetch(`/api/folders/${encodeURIComponent(currentEditFolderId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description, color }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to update folder');
    showToast(`Folder "${name}" updated`, 'success');
    closeModal('modal-folder-edit');
    await fetchFolders();
    await fetchProfiles();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

let currentDeleteFolderId = '';
function confirmDeleteFolder(id) {
  const f = savedFolders.find(x => x.id === id);
  if (!f) return;
  currentDeleteFolderId = id;
  document.getElementById('folder-delete-msg').textContent = `Are you sure you want to delete folder "${f.name}"? Profiles inside this folder will not be deleted; choose where to move them below:`;
  populateFolderSelects();
  openModal('modal-folder-delete');
}

document.getElementById('btn-confirm-delete-folder')?.addEventListener('click', async () => {
  if (!currentDeleteFolderId) return;
  const targetFolder = document.getElementById('folder-delete-target-select').value || 'default';

  try {
    const res = await fetch(`/api/folders/${encodeURIComponent(currentDeleteFolderId)}?move_to=${encodeURIComponent(targetFolder)}`, {
      method: 'DELETE',
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to delete folder');
    showToast(`Folder deleted. Profiles moved to "${targetFolder}"`, 'info');
    closeModal('modal-folder-delete');
    if (activeFolderFilter === currentDeleteFolderId) {
      activeFolderFilter = 'all';
    }
    await fetchFolders();
    await fetchProfiles();
    syncFolderFilterUI();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

// Folder Filter Dropdown
document.getElementById('folder-filter-select')?.addEventListener('change', (e) => {
  activeFolderFilter = e.target.value;
  syncFolderFilterUI();
  renderProfilesTable();
});

// Proxies Manager
document.getElementById('btn-manage-proxies')?.addEventListener('click', async () => {
  await fetchProxies();
  renderProxiesList();
  openModal('modal-proxies');
});

function renderProxiesList() {
  const container = document.getElementById('proxies-list-container');
  if (!savedProxies.length) {
    container.innerHTML = '<div style="color:var(--text-muted); font-size:13px; padding:12px 0;">No proxies added yet.</div>';
    return;
  }
  container.innerHTML = savedProxies.map(p => `
    <div style="display:flex; align-items:center; justify-content:space-between; padding:10px 12px; background:var(--bg-main); border:1px solid var(--border); border-radius:6px; margin-bottom:8px;">
      <div>
        <div style="font-weight:600; font-size:13.5px;">${esc(p.name)}</div>
        <div style="font-family:var(--font-mono); font-size:12px; color:var(--text-muted);">${esc(p.url)}</div>
        ${p.note ? `<div style="font-size:11px; color:var(--text-dim);">${esc(p.note)}</div>` : ''}
      </div>
      <div style="display:flex; align-items:center; gap:8px;">
        <button class="btn btn-secondary btn-sm" onclick="testProxyConnection('${esc(p.url)}', this)">Test</button>
        <button class="btn btn-danger btn-sm" onclick="deleteProxy('${esc(p.name)}')">Delete</button>
      </div>
    </div>
  `).join('');
}

async function testProxyConnection(url, btn) {
  btn.disabled = true;
  btn.textContent = 'Testing...';
  try {
    const res = await fetch('/api/proxies/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`Proxy OK: ${data.ip} (${data.latency_ms}ms)`, 'success');
    } else {
      showToast(`Proxy Error: ${data.message} (${data.latency_ms}ms)`, 'error');
    }
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Test';
  }
}

async function deleteProxy(name) {
  try {
    const res = await fetch(`/api/proxies/${encodeURIComponent(name)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete proxy');
    showToast(`Proxy "${name}" deleted`, 'info');
    await fetchProxies();
    renderProxiesList();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

document.getElementById('proxy-add-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('proxy-name-input').value.trim();
  const url = document.getElementById('proxy-url-input').value.trim();
  const note = document.getElementById('proxy-note-input').value.trim();

  try {
    const res = await fetch('/api/proxies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, url, note }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to add proxy');
    showToast(`Proxy "${name}" added`, 'success');
    document.getElementById('proxy-add-form').reset();
    await fetchProxies();
    renderProxiesList();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

// Import Archive
document.getElementById('btn-import-profile')?.addEventListener('click', () => {
  openModal('modal-import');
});

document.getElementById('import-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById('import-file');
  if (!fileInput.files.length) return;

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  try {
    showToast('Importing profile archive...', 'info');
    const res = await fetch('/api/profiles/import', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Import failed');
    showToast(`Profile "${data.profile.name}" imported successfully`, 'success');
    closeModal('modal-import');
    await fetchProfiles();
    await fetchTelemetry();
    await fetchFolders();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

// Search & Filter Tabs
document.getElementById('search-input')?.addEventListener('input', () => {
  renderProfilesTable();
});

document.querySelectorAll('.nav-link[data-filter]').forEach(link => {
  link.addEventListener('click', (e) => {
    e.preventDefault();
    document.querySelectorAll('.nav-link[data-filter]').forEach(l => l.classList.remove('active'));
    link.classList.add('active');
    activeFilter = link.dataset.filter;

    // Sync mobile filter pills
    document.querySelectorAll('.filter-pill[data-pill-filter]').forEach(p => {
      p.classList.toggle('active', p.dataset.pillFilter === activeFilter);
    });

    renderProfilesTable();
  });
});

// Mobile Filter Pills
document.querySelectorAll('.filter-pill[data-pill-filter]').forEach(pill => {
  pill.addEventListener('click', (e) => {
    e.preventDefault();
    document.querySelectorAll('.filter-pill[data-pill-filter]').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    activeFilter = pill.dataset.pillFilter;

    // Sync sidebar nav
    document.querySelectorAll('.sidebar-nav .nav-link[data-filter]').forEach(l => {
      l.classList.toggle('active', l.dataset.filter === activeFilter);
    });

    renderProfilesTable();
  });
});

// Mobile Drawer Handlers
function openSidebar() {
  document.getElementById('sidebar-drawer')?.classList.add('open');
  document.getElementById('sidebar-backdrop')?.classList.add('active');
}

function closeSidebar() {
  document.getElementById('sidebar-drawer')?.classList.remove('open');
  document.getElementById('sidebar-backdrop')?.classList.remove('active');
}

document.getElementById('btn-mobile-menu')?.addEventListener('click', openSidebar);
document.getElementById('btn-mobile-close')?.addEventListener('click', closeSidebar);
document.getElementById('sidebar-backdrop')?.addEventListener('click', closeSidebar);

// Close sidebar on navigation click on mobile
document.querySelectorAll('.sidebar-nav .nav-link').forEach(link => {
  link.addEventListener('click', () => {
    if (window.innerWidth <= 860) {
      closeSidebar();
    }
  });
});

// MCP AI Setup Modal Handler
document.getElementById('btn-mcp-config')?.addEventListener('click', () => {
  openModal('modal-mcp-config');
});

window.switchMcpTab = function(tabName) {
  document.querySelectorAll('.mcp-tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.mcp-tab-panel').forEach(p => p.classList.remove('active'));

  const activeBtn = document.getElementById(`tab-btn-${tabName}`);
  const activePanel = document.getElementById(`mcp-tab-${tabName}`);
  if (activeBtn) activeBtn.classList.add('active');
  if (activePanel) activePanel.classList.add('active');
};

window.copyMcpInput = async function(inputId) {
  const el = document.getElementById(inputId);
  if (!el) return;
  try {
    await navigator.clipboard.writeText(el.value);
    showToast('Copied to clipboard!', 'success');
  } catch {
    el.select();
    document.execCommand('copy');
    showToast('Copied to clipboard!', 'success');
  }
};

window.copyCodeSnippet = async function(codeId) {
  const el = document.getElementById(codeId);
  if (!el) return;
  try {
    await navigator.clipboard.writeText(el.innerText.trim());
    showToast('Configuration copied to clipboard!', 'success');
  } catch {
    showToast('Failed to copy. Please copy manually.', 'error');
  }
};

// Initial Load & Intervals
window.addEventListener('DOMContentLoaded', async () => {
  initColorPalettes();
  await fetchTelemetry();
  await fetchFolders();
  await fetchProxies();
  await fetchProfiles();
  setInterval(fetchTelemetry, 5000);
  setInterval(fetchProfiles, 10000);
  setInterval(fetchFolders, 10000);
});
