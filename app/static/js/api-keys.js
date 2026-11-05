(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const state = { keys: [], legacy: null, endpoint: '', loaded: false, loading: false, request: 0, target: null, catalog: [], profiles: [] };
  const readOnly = ['profiles.read', 'folders.read', 'browser.read'];
  const operator = [...readOnly, 'profiles.create', 'profiles.update', 'lifecycle.start', 'lifecycle.stop', 'lifecycle.restart', 'browser.control'];
  const globalPermissions = new Set(['folders.manage', 'proxies.read', 'proxies.manage', 'system.read']);
  const editors = new Map();
  const statuses = ['active', 'expired', 'revoked'];
  const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  let secret = '';
  let secretGeneration = 0;
  let dialogTrigger = null;

  function errorText(error) { return error instanceof Error ? error.message : 'Something went wrong. Please try again.'; }
  function showError(id, message = '') { $(id).textContent = message; $(id).hidden = !message; }
  function feedback(message) { $('ak-feedback').textContent = message; }
  function metadata(key) {
    return { id: key.id, name: key.name, prefix: key.prefix, status: key.status, created_at: key.created_at,
      expires_at: key.expires_at, last_used_at: key.last_used_at, revoked_at: key.revoked_at,
      permissions: Array.isArray(key.permissions) ? [...new Set(key.permissions.filter((id) => typeof id === 'string'))] : null,
      profile_access: key.profile_access,
      profiles: Array.isArray(key.profiles) ? key.profiles.filter((name) => typeof name === 'string') : [],
      folders: Array.isArray(key.folders) ? key.folders.filter((id) => typeof id === 'string') : [] };
  }
  function statusOf(key) {
    if (key.status === 'revoked' || key.revoked_at != null) return 'revoked';
    if (key.status === 'expired' || (key.expires_at != null && key.expires_at * 1000 <= Date.now())) return 'expired';
    return statuses.includes(key.status) ? key.status : 'unavailable';
  }
  function label(value) { return value.charAt(0).toUpperCase() + value.slice(1); }
  function date(value, fallback) {
    if (value == null) return fallback;
    const parsed = new Date(value * 1000);
    return Number.isNaN(parsed.getTime()) ? 'Unavailable' : dateFormat.format(parsed);
  }
  async function api(path = '', method = 'GET', body) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 20000);
    try {
      const options = { method, credentials: 'same-origin', cache: 'no-store', signal: controller.signal, headers: { Accept: 'application/json' } };
      if (method !== 'GET') {
        options.headers['X-ProfileStack-Management'] = '1';
        options.headers['Content-Type'] = 'application/json';
        if (body !== undefined) options.body = JSON.stringify(body);
      }
      const response = await fetch(`/api/api-keys${path}`, options);
      if (response.status === 401 || (response.redirected && new URL(response.url).pathname === '/login')) {
        clearSecret();
        window.location.assign('/login');
        throw new Error('Your session expired. Redirecting to sign in…');
      }
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : `Request failed (${response.status}). Please try again.`);
      if (!data) throw new Error('The server returned an unreadable response. Refresh the list before retrying.');
      return data;
    } catch (error) {
      if (error.name === 'AbortError' || error instanceof TypeError) {
        throw new Error(method === 'GET' ? 'Unable to load API keys. Check your connection and retry.' : 'The request could not be confirmed. Refresh the list before retrying; the change may have completed.');
      }
      throw error;
    } finally { clearTimeout(timer); }
  }
  function cell(row, title, content) {
    const td = document.createElement('td');
    td.dataset.label = title;
    if (content instanceof Node) td.append(content); else td.textContent = content;
    row.append(td);
  }
  function button(text, className, callback, name) {
    const element = document.createElement('button');
    element.type = 'button'; element.className = `btn ${className}`; element.textContent = text;
    element.setAttribute('aria-label', `${text} ${name}`); element.addEventListener('click', callback);
    return element;
  }
  function badge(status) {
    const element = document.createElement('span');
    element.className = `ak-status ak-status-${status}`; element.textContent = label(status);
    return element;
  }
  function render() {
    const counts = { active: 0, expired: 0, revoked: 0 };
    const rows = document.createDocumentFragment();
    state.keys.forEach((key) => {
      const status = statusOf(key);
      if (status in counts) counts[status]++;
      const row = document.createElement('tr');
      const identity = document.createElement('div');
      const name = document.createElement('span'); name.className = 'ak-key-name'; name.textContent = key.name;
      const prefix = document.createElement('code'); prefix.className = 'ak-key-prefix'; prefix.textContent = key.prefix;
      const access = document.createElement('span'); access.className = 'ak-key-access';
      const boundary = key.profile_access === 'all' ? 'All profiles' : key.profile_access === 'group'
        ? (key.folders && key.folders.length
            ? `Group: ${key.folders.map((fid) => (state.folders.find((f) => f.id === fid) || {}).name || fid).join(', ')}`
            : 'Group-scoped')
        : key.profile_access === 'selected'
        ? `${key.profiles.length} selected profile${key.profiles.length === 1 ? '' : 's'}` : 'Profile access unavailable';
      access.textContent = `${key.permissions ? `${key.permissions.length} permission${key.permissions.length === 1 ? '' : 's'}` : 'Permissions unavailable'} · ${boundary}`;
      identity.append(name, prefix, access);
      cell(row, 'Name / prefix', identity); cell(row, 'Status', badge(status));
      cell(row, 'Created', date(key.created_at, 'Unavailable'));
      cell(row, 'Expires', date(key.expires_at, 'Never'));
      cell(row, 'Last used', date(key.last_used_at, 'Never'));
      const actions = document.createElement('div'); actions.className = 'ak-actions';
      actions.append(button('Rename', 'btn-secondary', () => openRename(key), key.name));
      const editAccess = button('Edit access', 'btn-secondary', () => openAccess(key), key.name);
      editAccess.disabled = !state.catalog.length || !key.permissions || !['all', 'selected', 'group'].includes(key.profile_access);
      actions.append(editAccess);
      if (status !== 'revoked') actions.append(button('Revoke', 'btn-danger', () => openRevoke(key), key.name));
      else { const note = document.createElement('span'); note.className = 'ak-muted'; note.textContent = 'Access removed'; actions.append(note); }
      cell(row, 'Actions', actions); rows.append(row);
    });
    $('ak-rows').replaceChildren(rows);
    statuses.forEach((status) => { $(`ak-${status}-count`).textContent = state.loaded ? counts[status] : '—'; });
    $('ak-table').hidden = !state.loaded || !state.keys.length;
    $('ak-empty').hidden = !state.loaded || state.keys.length > 0;
    const legacyStatus = ['active', 'revoked', 'unavailable'].includes(state.legacy?.status) ? state.legacy.status : 'unavailable';
    $('ak-legacy-status').textContent = state.loaded ? label(legacyStatus) : 'Not loaded';
    $('ak-legacy-status').className = `ak-status ak-status-${legacyStatus}`;
    $('ak-revoke-legacy').disabled = !state.loaded || legacyStatus !== 'active';
    $('ak-revoke-legacy').textContent = legacyStatus === 'revoked' ? 'Legacy key disabled' : 'Disable legacy key';
    $('ak-endpoint').textContent = state.endpoint || 'Endpoint unavailable until keys are loaded.';
    $('ak-copy-endpoint').disabled = !state.endpoint;
  }
  async function loadKeys() {
    const request = ++state.request;
    state.loading = true;
    $('ak-list').setAttribute('aria-busy', 'true'); $('ak-refresh').disabled = true; $('ak-retry').disabled = true;
    $('ak-loading').hidden = state.loaded; showError('ak-load-error-text'); $('ak-load-error').hidden = true;
    try {
      const data = await api();
      if (request !== state.request) return;
      if (!Array.isArray(data.keys) || !data.legacy || typeof data.endpoint !== 'string'
        || !Array.isArray(data.permission_catalog) || !data.permission_catalog.length
        || !data.permission_catalog.every((item) => typeof item.id === 'string' && typeof item.label === 'string' && typeof item.group === 'string')
        || !Array.isArray(data.available_profiles) || !data.available_profiles.every((item) => typeof item.name === 'string')) {
        throw new Error('Permissions or profiles could not be loaded. Retry loading API keys.');
      }
      state.catalog = data.permission_catalog.map(({ id, label, group }) => ({ id, label, group }));
      state.profiles = data.available_profiles.map(({ name, folder }) => ({ name, folder: typeof folder === 'string' ? folder : '' }));
      state.folders = Array.isArray(data.available_folders) ? data.available_folders.map(({ id, name, color }) => ({ id, name, color: typeof color === 'string' ? color : '#64748b' })) : [];
      state.keys = data.keys.map(metadata); state.legacy = metadata(data.legacy);
      const endpoint = new URL(data.endpoint, window.location.origin);
      state.endpoint = endpoint.origin === window.location.origin ? endpoint.href : new URL('/mcp/sse', window.location.origin).href;
      state.loaded = true; render();
      $('ak-create').disabled = false;
    } catch (error) {
      if (request !== state.request) return;
      $('ak-load-error-text').textContent = `${state.loaded ? 'Showing the last loaded data. ' : ''}${errorText(error)}`;
      $('ak-load-error').hidden = false;
      if (!state.loaded) render();
    } finally {
      if (request === state.request) {
        state.loading = false; $('ak-loading').hidden = true; $('ak-list').setAttribute('aria-busy', 'false');
        $('ak-refresh').disabled = false; $('ak-retry').disabled = false;
      }
    }
  }
  function openDialog(id, trigger = document.activeElement) {
    dialogTrigger = trigger;
    const dialog = $(id); dialog.showModal();
    const focus = dialog.querySelector('[autofocus]'); if (focus) focus.focus();
    dialog.scrollTop = 0;
  }
  function clearSecret() {
    secretGeneration++; secret = ''; $('ak-secret').value = ''; $('ak-secret').textContent = '';
    $('ak-copy-status').textContent = ''; $('ak-copy-secret').disabled = false;
  }
  function busy(dialog, value, submitId, text) {
    dialog.dataset.busy = value ? 'true' : 'false'; dialog.setAttribute('aria-busy', String(value));
    dialog.querySelectorAll('button, input, select').forEach((element) => { element.disabled = value; });
    $(submitId).textContent = text;
    if (!value) dialog.querySelectorAll('.ak-access-editor').forEach((root) => editors.get(root.id)?.sync());
  }
  function makeElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }
  function buildEditor(id, policy) {
    const root = $(id); root.replaceChildren();
    const permissions = new Set(policy.permissions || []);
    const selected = new Set(policy.profiles || []);
    const selectedFolders = new Set(policy.folders || []);
    let scope = policy.profile_access === 'group' ? 'group' : policy.profile_access === 'all' ? 'all' : 'selected';
    const permissionInputs = new Map();
    const presets = makeElement('div', 'ak-presets');
    presets.setAttribute('role', 'group'); presets.setAttribute('aria-label', 'Permission presets');
    const summary = makeElement('p', 'ak-muted'); summary.setAttribute('role', 'status');
    const groups = makeElement('div', 'ak-permission-groups');
    const fieldsets = new Map();
    state.catalog.forEach((permission) => {
      if (!fieldsets.has(permission.group)) {
        const fieldset = makeElement('fieldset', 'ak-permission-group');
        fieldset.append(makeElement('legend', '', permission.group)); groups.append(fieldset); fieldsets.set(permission.group, fieldset);
      }
      const choice = makeElement('label', 'ak-choice');
      const input = makeElement('input'); input.type = 'checkbox'; input.value = permission.id;
      const copy = makeElement('span'); copy.append(makeElement('span', '', permission.label), makeElement('code', 'ak-permission-id', permission.id));
      choice.append(input, copy); fieldsets.get(permission.group).append(choice); permissionInputs.set(permission.id, input);
      input.addEventListener('change', () => { if (input.checked) permissions.add(permission.id); else permissions.delete(permission.id); sync(); });
    });
    const boundary = makeElement('fieldset', 'ak-boundary'); boundary.append(makeElement('legend', '', 'Profile boundary'));
    const scopes = makeElement('div', 'ak-scope-choices'); const scopeInputs = new Map();
    [['all', 'All profiles'], ['group', 'Specific group / folder'], ['selected', 'Selected profiles']].forEach(([value, text]) => {
      const choice = makeElement('label', 'ak-choice'); const input = makeElement('input');
      input.type = 'radio'; input.name = `${id}-scope`; input.value = value;
      input.addEventListener('change', () => { scope = value; sync(); });
      scopeInputs.set(value, input); choice.append(input, makeElement('span', '', text)); scopes.append(choice);
    });
    const globalNote = makeElement('p', 'ak-muted', 'Folder management, proxy permissions and system tools require all-profile access. Restricting to a specific group or selected profiles removes these permissions.');
    globalNote.id = `${id}-global-note`;
    globalPermissions.forEach((permission) => permissionInputs.get(permission)?.setAttribute('aria-describedby', globalNote.id));

    const groupSection = makeElement('div', 'ak-group-section');
    const groupNote = makeElement('p', 'ak-muted', 'The key can only create, edit, delete, and control profiles inside the assigned group. It cannot access or move profiles outside this group.');
    const groupList = makeElement('div', 'ak-group-list');
    groupList.setAttribute('role', 'group'); groupList.setAttribute('aria-label', 'Assigned groups or folders');
    const availableFolders = state.folders && state.folders.length ? state.folders : [{ id: 'default', name: 'General', color: '#64748b' }];
    availableFolders.forEach((folder) => {
      const choice = makeElement('label', 'ak-choice'); const input = makeElement('input');
      input.type = 'checkbox'; input.value = folder.id; input.checked = selectedFolders.has(folder.id);
      input.addEventListener('change', () => {
        if (input.checked) selectedFolders.add(folder.id);
        else selectedFolders.delete(folder.id);
        sync();
      });
      const copy = makeElement('span');
      const dot = makeElement('span', 'ak-folder-dot');
      if (folder.color) dot.style.backgroundColor = folder.color;
      copy.append(dot, makeElement('span', '', folder.name), makeElement('code', 'ak-permission-id', folder.id));
      choice.append(input, copy); groupList.append(choice);
    });
    const groupCount = makeElement('p', 'ak-muted'); groupCount.setAttribute('role', 'status');
    groupSection.append(groupNote, groupCount, groupList);

    const profileSection = makeElement('div', 'ak-profile-section');
    const searchLabel = makeElement('label', '', 'Search profiles'); searchLabel.htmlFor = `${id}-search`;
    const search = makeElement('input', 'ak-input'); search.id = searchLabel.htmlFor; search.type = 'search'; search.placeholder = 'Search by profile name or folder'; search.autocomplete = 'off';
    const count = makeElement('p', 'ak-muted'); count.setAttribute('role', 'status');
    const list = makeElement('div', 'ak-profile-list'); list.setAttribute('role', 'group'); list.setAttribute('aria-label', 'Profiles this key can access');
    const available = new Map(state.profiles.map((profile) => [profile.name, profile]));
    selected.forEach((name) => { if (!available.has(name)) available.set(name, { name, folder: 'Not currently available' }); });
    const profileRows = [];
    available.forEach((profile) => {
      const choice = makeElement('label', 'ak-choice'); const input = makeElement('input'); input.type = 'checkbox'; input.checked = selected.has(profile.name);
      input.addEventListener('change', () => { if (input.checked) selected.add(profile.name); else selected.delete(profile.name); sync(); });
      const copy = makeElement('span'); copy.append(makeElement('span', '', profile.name));
      if (profile.folder) copy.append(makeElement('small', 'ak-profile-folder', profile.folder));
      choice.append(input, copy); list.append(choice); profileRows.push({ choice, text: `${profile.name} ${profile.folder}`.toLocaleLowerCase() });
    });
    const empty = makeElement('p', 'ak-muted');
    function filterProfiles() {
      const query = search.value.trim().toLocaleLowerCase(); let visible = 0;
      profileRows.forEach(({ choice, text }) => { choice.hidden = !text.includes(query); if (!choice.hidden) visible++; });
      empty.textContent = profileRows.length ? 'No profiles match your search.' : 'No profiles are available yet.';
      empty.hidden = visible > 0;
    }
    search.addEventListener('input', filterProfiles);
    const selectionNote = makeElement('p', 'ak-muted', 'Zero selected profiles means no access to existing profiles. Profiles created by this key are automatically assigned to it.');
    const allNote = makeElement('p', 'ak-muted', 'Includes every current and future profile across all groups. Permissions above still limit the available operations.');
    profileSection.append(searchLabel, search, count, list, empty, selectionNote);
    boundary.append(scopes, allNote, groupSection, profileSection);
    const presetButtons = new Map();
    [['Read-only', readOnly], ['Operator', operator], ['Full', state.catalog.map((item) => item.id)]].forEach(([text, ids]) => {
      const preset = button(text, 'btn-secondary', () => {
        permissions.clear(); ids.forEach((permission) => { if (permissionInputs.has(permission)) permissions.add(permission); });
        if (text === 'Full') scope = 'all'; sync();
      }, 'permission preset');
      preset.setAttribute('aria-describedby', `${id}-preset-note`); presetButtons.set(text, { preset, ids }); presets.append(preset);
    });
    const presetNote = makeElement('p', 'ak-muted', 'Read-only: profile, folder and browser reads. Operator adds profile create/update, lifecycle and browser control. Full selects all permissions and all profiles; other presets keep the profile boundary.');
    presetNote.id = `${id}-preset-note`;
    function sync() {
      const isBusy = root.closest('dialog').dataset.busy === 'true';
      if (scope !== 'all') globalPermissions.forEach((permission) => permissions.delete(permission));
      permissionInputs.forEach((input, permission) => {
        input.checked = permissions.has(permission); input.disabled = isBusy || (scope !== 'all' && globalPermissions.has(permission));
      });
      scopeInputs.forEach((input, value) => { input.checked = scope === value; });
      presetButtons.forEach(({ preset, ids }, text) => preset.setAttribute('aria-pressed', String(ids.length === permissions.size && ids.every((permission) => permissions.has(permission)) && (text !== 'Full' || scope === 'all'))));
      groupSection.hidden = scope !== 'group';
      profileSection.hidden = scope !== 'selected';
      allNote.hidden = scope !== 'all';
      summary.textContent = `${permissions.size} permission${permissions.size === 1 ? '' : 's'} selected${permissions.size ? '' : ' — this key cannot call any operations'}.`;
      count.textContent = `${selected.size} profile${selected.size === 1 ? '' : 's'} selected.`;
      groupCount.textContent = `${selectedFolders.size} group${selectedFolders.size === 1 ? '' : 's'} assigned.`;
      filterProfiles();
    }
    root.append(makeElement('h3', 'ak-editor-title', 'Permissions'), presets, presetNote, summary, groups, globalNote, boundary);
    const editor = {
      sync,
      value: () => {
        if (scope === 'group' && selectedFolders.size === 0 && availableFolders.length) {
          selectedFolders.add(availableFolders[0].id);
        }
        return {
          permissions: [...permissions],
          profile_access: scope,
          profiles: scope === 'selected' ? [...selected] : [],
          folders: scope === 'group' ? [...selectedFolders] : []
        };
      }
    };
    editors.set(id, editor); sync(); return editor;
  }
  function openAccess(key) {
    state.target = metadata(key); showError('ak-access-error'); $('ak-access-key').textContent = key.name;
    buildEditor('ak-edit-access', key); openDialog('ak-access-dialog');
  }
  function openRename(key) {
    state.target = metadata(key); showError('ak-rename-error'); $('ak-rename-name').value = key.name;
    openDialog('ak-rename-dialog'); $('ak-rename-name').select();
  }
  function openRevoke(key) {
    state.target = metadata(key); showError('ak-revoke-error');
    const legacy = key.id === 'legacy';
    $('ak-revoke-title').textContent = legacy ? 'Disable legacy server key?' : 'Revoke API key?';
    $('ak-revoke-description').textContent = legacy
      ? 'Disable the legacy server key only after migrating all existing clients to named keys. Any client still using it will stop working.'
      : `Revoke “${key.name}”? This removes all access granted to this key. The key’s metadata will remain visible.`;
    $('ak-revoke-submit').textContent = legacy ? 'Disable legacy key' : 'Revoke key';
    openDialog('ak-revoke-dialog');
  }
  function readName(id) {
    const input = $(id); input.setCustomValidity(''); const value = input.value.trim();
    if (!value) { input.setCustomValidity('Enter a key name, not just spaces.'); input.reportValidity(); return null; }
    return value;
  }
  ['ak-create-name', 'ak-rename-name'].forEach((id) => $(id).addEventListener('input', () => $(id).setCustomValidity('')));
  document.querySelectorAll('.ak-dialog').forEach((dialog) => {
    dialog.addEventListener('keydown', (event) => {
      if (event.key !== 'Tab') return;
      const controls = [...dialog.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled)')].filter((element) => element.getClientRects().length > 0);
      const first = controls[0], last = controls[controls.length - 1];
      if (!first) { event.preventDefault(); return; }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === $('ak-access-title'))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    dialog.querySelectorAll('[data-dismiss]').forEach((element) => element.addEventListener('click', () => {
      if (dialog.dataset.busy === 'true') return;
      if (dialog.id === 'ak-secret-dialog') clearSecret();
      dialog.close();
    }));
    dialog.addEventListener('cancel', (event) => {
      if (dialog.dataset.busy === 'true') event.preventDefault();
      else if (dialog.id === 'ak-secret-dialog') clearSecret();
    });
    dialog.addEventListener('close', () => {
      if (dialog.id === 'ak-secret-dialog') clearSecret();
      if (dialog.id === 'ak-create-dialog') { $('ak-create-form').reset(); $('ak-create-name').setCustomValidity(''); }
      if (['ak-rename-dialog', 'ak-revoke-dialog', 'ak-access-dialog'].includes(dialog.id)) state.target = null;
      if (!document.querySelector('dialog[open]')) {
        if (dialogTrigger?.isConnected) dialogTrigger.focus(); else $('ak-create').focus();
      }
    });
  });
  $('ak-create').addEventListener('click', () => {
    if (!state.loaded) return;
    showError('ak-create-error'); buildEditor('ak-create-access', { permissions: readOnly, profile_access: 'all', profiles: [] }); openDialog('ak-create-dialog');
  });
  $('ak-refresh').addEventListener('click', loadKeys); $('ak-retry').addEventListener('click', loadKeys);
  $('ak-revoke-legacy').addEventListener('click', () => { if (state.legacy?.status === 'active') openRevoke(state.legacy); });
  $('ak-create-form').addEventListener('submit', async (event) => {
    event.preventDefault(); const dialog = $('ak-create-dialog'); if (dialog.dataset.busy === 'true') return;
    const name = readName('ak-create-name'); if (!name) return;
    const expiration = $('ak-expiration').value;
    const policy = editors.get('ak-create-access').value();
    showError('ak-create-error'); busy(dialog, true, 'ak-create-submit', 'Creating…');
    try {
      const data = await api('', 'POST', { name, expires_in_days: expiration === 'never' ? null : Number(expiration), ...policy });
      if (!data.key || typeof data.secret !== 'string' || !data.secret) throw new Error('The key may have been created, but its secret was not received. Refresh the list and revoke the key before creating a replacement.');
      state.keys = [metadata(data.key), ...state.keys.filter((key) => key.id !== data.key.id)];
      if (state.loaded) render();
      clearSecret(); secret = data.secret; data.secret = null; $('ak-secret').value = secret;
      dialog.close(); openDialog('ak-secret-dialog', $('ak-create')); feedback('API key created. Save its secret now.');
      await loadKeys();
    } catch (error) { showError('ak-create-error', errorText(error)); }
    finally { busy(dialog, false, 'ak-create-submit', 'Create key'); }
  });
  $('ak-access-form').addEventListener('submit', async (event) => {
    event.preventDefault(); const dialog = $('ak-access-dialog'); if (dialog.dataset.busy === 'true' || !state.target) return;
    const id = state.target.id; const policy = editors.get('ak-edit-access').value();
    showError('ak-access-error'); busy(dialog, true, 'ak-access-submit', 'Saving…');
    try {
      const data = await api(`/${encodeURIComponent(id)}/permissions`, 'PATCH', policy);
      if (!data.key || !Array.isArray(data.key.permissions)) throw new Error('Access could not be confirmed. Refresh the list before retrying.');
      state.keys = state.keys.map((key) => key.id === id ? metadata(data.key) : key);
      render(); dialog.close(); feedback('API key access updated for subsequent calls. Its secret and revocation status are unchanged.'); await loadKeys();
    } catch (error) { showError('ak-access-error', errorText(error)); }
    finally { busy(dialog, false, 'ak-access-submit', 'Save access'); }
  });
  $('ak-rename-form').addEventListener('submit', async (event) => {
    event.preventDefault(); const dialog = $('ak-rename-dialog'); if (dialog.dataset.busy === 'true' || !state.target) return;
    const name = readName('ak-rename-name'); if (!name) return;
    const id = state.target.id; showError('ak-rename-error'); busy(dialog, true, 'ak-rename-submit', 'Saving…');
    try {
      const data = await api(`/${encodeURIComponent(id)}`, 'PATCH', { name });
      if (!data.key) throw new Error('The name could not be confirmed. Refresh the list before retrying.');
      state.keys = state.keys.map((key) => key.id === id ? metadata(data.key) : key);
      render(); dialog.close(); feedback('API key renamed. Its secret is unchanged.'); await loadKeys();
    } catch (error) { showError('ak-rename-error', errorText(error)); }
    finally { busy(dialog, false, 'ak-rename-submit', 'Save name'); }
  });
  $('ak-revoke-form').addEventListener('submit', async (event) => {
    event.preventDefault(); const dialog = $('ak-revoke-dialog'); if (dialog.dataset.busy === 'true' || !state.target) return;
    const id = state.target.id; const legacy = id === 'legacy';
    showError('ak-revoke-error'); busy(dialog, true, 'ak-revoke-submit', legacy ? 'Disabling…' : 'Revoking…');
    try {
      const data = await api(`/${encodeURIComponent(id)}`, 'DELETE');
      if (data.revoked !== true) throw new Error('Revocation could not be confirmed. Refresh the list before retrying.');
      if (legacy) state.legacy.status = 'revoked';
      else state.keys = state.keys.map((key) => key.id === id ? { ...key, status: 'revoked' } : key);
      render(); dialog.close(); feedback(legacy ? 'Legacy key disabled. Existing clients must use a named key.' : 'API key revoked. Its access has been removed.'); await loadKeys();
    } catch (error) { showError('ak-revoke-error', errorText(error)); }
    finally { busy(dialog, false, 'ak-revoke-submit', legacy ? 'Disable legacy key' : 'Revoke key'); }
  });
  $('ak-copy-secret').addEventListener('click', async () => {
    if (!secret) return; const generation = secretGeneration;
    try {
      await navigator.clipboard.writeText(secret);
      if (generation === secretGeneration && $('ak-secret-dialog').open) $('ak-copy-status').textContent = 'Secret copied. Store it securely.';
    } catch {
      if (generation !== secretGeneration || !$('ak-secret-dialog').open) return;
      $('ak-copy-status').textContent = 'Clipboard unavailable. Select and copy the secret manually.';
      $('ak-secret').focus(); $('ak-secret').select();
    }
  });
  $('ak-copy-endpoint').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(state.endpoint); feedback('SSE endpoint copied.'); }
    catch { feedback('Clipboard unavailable. Select and copy the endpoint manually.'); }
  });
  window.addEventListener('pagehide', clearSecret);
  // Expiry transitions and last-used timestamps stay current without stealing dialog focus.
  setInterval(() => { if (!document.hidden && !document.querySelector('dialog[open]') && !state.loading) loadKeys(); }, 60000);
  loadKeys();
})();
