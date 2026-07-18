/* storage.js — Postgres-backed CRUD via /api, with an in-memory cache that
 * preserves the original synchronous GS.Journal / GS.Todo surface.
 *
 * Model:
 *   - getAll/getById  : synchronous reads from an in-memory cache.
 *   - create/update/remove/toggle/clearCompleted : optimistic — mutate the
 *     cache immediately (sync return) AND enqueue an async API write.
 *   - GS.ready()      : call on pages that render lists (journal/todos). It
 *     ensures auth (login gate) + hydrates the cache from the API once.
 *   - A one-time migration imports pre-existing localStorage entries into the DB.
 *
 * Used by: journal.html, todos.html, analytics.html, records.html
 */
(function (window) {
  'use strict';

  var API_BASE = (window.GS_API_BASE || '/api').replace(/\/$/, '');
  var TOKEN_KEY = 'gs_api_token';
  var MIGRATED_KEY = 'gs_migrated_v1';
  var LEGACY_JOURNAL_KEY = 'gitsweaty_journal';
  var LEGACY_TODOS_KEY = 'gitsweaty_todos';

  // ── In-memory caches ───────────────────────────────────────────────────────
  var journalCache = [];
  var todoCache = [];
  var readyPromise = null;

  // ── ID generation (frontend-owned so optimistic id == server id) ───────────
  function genId(prefix) {
    return prefix + '_' + Date.now() + '_' + Math.random().toString(16).slice(2, 6);
  }

  // ── Token helpers ──────────────────────────────────────────────────────────
  function getToken() { try { return localStorage.getItem(TOKEN_KEY) || ''; } catch (e) { return ''; } }
  function setToken(t) { try { localStorage.setItem(TOKEN_KEY, t); } catch (e) {} }
  function clearToken() { try { localStorage.removeItem(TOKEN_KEY); } catch (e) {} }

  function apiFetch(path, opts) {
    opts = opts || {};
    var headers = opts.headers || {};
    headers['Authorization'] = 'Bearer ' + getToken();
    if (opts.body && typeof opts.body !== 'string') {
      headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    opts.headers = headers;
    return fetch(API_BASE + path, opts);
  }

  // ── Login gate ─────────────────────────────────────────────────────────────
  function verifyToken(token) {
    return fetch(API_BASE + '/session', { headers: { 'Authorization': 'Bearer ' + token } })
      .then(function (r) { return r.ok; })
      .catch(function () { return false; });
  }

  function promptLogin(message) {
    injectStyle();
    return new Promise(function (resolve, reject) {
      var overlay = document.createElement('div');
      overlay.className = 'gs-modal-overlay';
      overlay.innerHTML =
        '<div class="gs-modal">' +
          '<h3>Unlock Journal &amp; Todos</h3>' +
          '<div class="gs-activity-info">' + escH(message || 'Enter your access password to sync with the database.') + '</div>' +
          '<label>Password</label>' +
          '<input type="password" id="gsPw" placeholder="Access password..." />' +
          '<div id="gsPwErr" style="color:#f87171;font-size:11px;margin:-6px 0 10px;display:none">Wrong password. Try again.</div>' +
          '<div class="gs-modal-actions">' +
            '<button class="gs-btn-save" id="gsPwOk">Unlock</button>' +
          '</div>' +
        '</div>';
      document.body.appendChild(overlay);
      var input = overlay.querySelector('#gsPw');
      var err = overlay.querySelector('#gsPwErr');
      var btn = overlay.querySelector('#gsPwOk');
      function submit() {
        var pw = input.value.trim();
        if (!pw) return;
        btn.disabled = true; btn.textContent = 'Checking...';
        verifyToken(pw).then(function (ok) {
          if (ok) {
            setToken(pw);
            overlay.remove();
            resolve(pw);
          } else {
            btn.disabled = false; btn.textContent = 'Unlock';
            err.style.display = 'block';
            input.select();
          }
        });
      }
      btn.addEventListener('click', submit);
      input.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });
      setTimeout(function () { input.focus(); }, 50);
    });
  }

  // Ensure we have a valid token (prompting if needed).
  function ensureAuth() {
    var tok = getToken();
    if (!tok) return promptLogin();
    return verifyToken(tok).then(function (ok) {
      if (ok) return tok;
      clearToken();
      return promptLogin('Session expired or password changed. Enter your password again.');
    });
  }

  // ── Hydration + one-time migration ─────────────────────────────────────────
  function hydrate() {
    return Promise.all([
      apiFetch('/journal').then(function (r) { return r.ok ? r.json() : { items: [] }; }),
      apiFetch('/todos').then(function (r) { return r.ok ? r.json() : { items: [] }; })
    ]).then(function (res) {
      journalCache = (res[0].items || []);
      todoCache = (res[1].items || []);
    });
  }

  function readLegacy(key) {
    try { return JSON.parse(localStorage.getItem(key)) || []; } catch (e) { return []; }
  }

  function migrateLegacy() {
    var done;
    try { done = localStorage.getItem(MIGRATED_KEY); } catch (e) { done = '1'; }
    if (done) return Promise.resolve();
    var oldJournal = readLegacy(LEGACY_JOURNAL_KEY);
    var oldTodos = readLegacy(LEGACY_TODOS_KEY);
    if (!oldJournal.length && !oldTodos.length) {
      try { localStorage.setItem(MIGRATED_KEY, '1'); } catch (e) {}
      return Promise.resolve();
    }
    var jobs = [];
    if (oldJournal.length) {
      jobs.push(apiFetch('/journal', { method: 'POST', body: { items: oldJournal } }));
    }
    if (oldTodos.length) {
      jobs.push(apiFetch('/todos', { method: 'POST', body: { items: oldTodos } }));
    }
    return Promise.all(jobs).then(function (rs) {
      var allOk = rs.every(function (r) { return r.ok; });
      if (allOk) {
        try { localStorage.setItem(MIGRATED_KEY, '1'); } catch (e) {}
        // Keep the legacy localStorage as a backup; do not delete.
      }
    });
  }

  // Public: ensure auth + hydrate + migrate exactly once.
  function ready() {
    if (readyPromise) return readyPromise;
    readyPromise = ensureAuth()
      .then(migrateLegacy)
      .then(hydrate)
      .catch(function (e) {
        readyPromise = null; // allow retry
        throw e;
      });
    return readyPromise;
  }

  // Fire-and-forget API write; on failure surface a toast and log.
  function pushWrite(promiseFactory) {
    ready().then(function () {
      return promiseFactory();
    }).then(function (r) {
      if (r && !r.ok) throw new Error('HTTP ' + r.status);
    }).catch(function (e) {
      showSyncError();
      if (window.console) console.error('[storage] sync failed:', e);
    });
  }

  var syncErrShown = false;
  function showSyncError() {
    if (syncErrShown) return;
    syncErrShown = true;
    setTimeout(function () { syncErrShown = false; }, 4000);
    var t = document.createElement('div');
    t.textContent = 'Sync failed — changes may not be saved to the database.';
    t.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#7f1d1d;color:#fff;padding:10px 16px;border-radius:8px;font-family:monospace;font-size:12px;z-index:2000';
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 3800);
  }

  // ── Journal CRUD (optimistic cache + async API) ────────────────────────────
  var Journal = {
    getAll: function () { return journalCache.slice(); },
    getById: function (id) { return journalCache.find(function (j) { return j.id === id; }) || null; },
    create: function (entry) {
      var now = new Date().toISOString();
      var item = {
        id: genId('j'), created_at: now, updated_at: now,
        title: entry.title || '', body: entry.body || '',
        activity_id: entry.activity_id || null, activity_date: entry.activity_date || null,
        activity_name: entry.activity_name || null, tags: entry.tags || [],
        source: entry.source || 'manual'
      };
      journalCache.unshift(item);
      pushWrite(function () { return apiFetch('/journal', { method: 'POST', body: item }); });
      return item;
    },
    update: function (id, changes) {
      var idx = journalCache.findIndex(function (j) { return j.id === id; });
      if (idx === -1) return null;
      Object.keys(changes).forEach(function (k) { journalCache[idx][k] = changes[k]; });
      journalCache[idx].updated_at = new Date().toISOString();
      pushWrite(function () { return apiFetch('/journal?id=' + encodeURIComponent(id), { method: 'PATCH', body: changes }); });
      return journalCache[idx];
    },
    remove: function (id) {
      journalCache = journalCache.filter(function (j) { return j.id !== id; });
      pushWrite(function () { return apiFetch('/journal?id=' + encodeURIComponent(id), { method: 'DELETE' }); });
    }
  };

  // ── Todo CRUD ──────────────────────────────────────────────────────────────
  var Todo = {
    getAll: function () { return todoCache.slice(); },
    getById: function (id) { return todoCache.find(function (t) { return t.id === id; }) || null; },
    create: function (entry) {
      var now = new Date().toISOString();
      var item = {
        id: genId('t'), created_at: now, updated_at: now,
        text: entry.text || '', done: false, done_at: null,
        priority: entry.priority || 'medium', due_date: entry.due_date || null,
        source: entry.source || 'manual', source_detail: entry.source_detail || null
      };
      todoCache.unshift(item);
      pushWrite(function () { return apiFetch('/todos', { method: 'POST', body: item }); });
      return item;
    },
    update: function (id, changes) {
      var idx = todoCache.findIndex(function (t) { return t.id === id; });
      if (idx === -1) return null;
      Object.keys(changes).forEach(function (k) { todoCache[idx][k] = changes[k]; });
      todoCache[idx].updated_at = new Date().toISOString();
      pushWrite(function () { return apiFetch('/todos?id=' + encodeURIComponent(id), { method: 'PATCH', body: changes }); });
      return todoCache[idx];
    },
    toggle: function (id) {
      var idx = todoCache.findIndex(function (t) { return t.id === id; });
      if (idx === -1) return null;
      todoCache[idx].done = !todoCache[idx].done;
      todoCache[idx].done_at = todoCache[idx].done ? new Date().toISOString() : null;
      todoCache[idx].updated_at = new Date().toISOString();
      var changes = { done: todoCache[idx].done, done_at: todoCache[idx].done_at };
      pushWrite(function () { return apiFetch('/todos?id=' + encodeURIComponent(id), { method: 'PATCH', body: changes }); });
      return todoCache[idx];
    },
    remove: function (id) {
      todoCache = todoCache.filter(function (t) { return t.id !== id; });
      pushWrite(function () { return apiFetch('/todos?id=' + encodeURIComponent(id), { method: 'DELETE' }); });
    },
    clearCompleted: function () {
      todoCache = todoCache.filter(function (t) { return !t.done; });
      pushWrite(function () { return apiFetch('/todos?action=clearCompleted', { method: 'POST', body: {} }); });
    }
  };

  // ── Export / Import ────────────────────────────────────────────────────────
  function exportData() {
    var blob = new Blob([JSON.stringify({
      journal: Journal.getAll(), todos: Todo.getAll(), exported_at: new Date().toISOString()
    }, null, 2)], { type: 'application/json' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'gitsweaty_data_' + new Date().toISOString().slice(0, 10) + '.json';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function importData(file, callback) {
    var reader = new FileReader();
    reader.onload = function (e) {
      try {
        var data = JSON.parse(e.target.result);
        ready().then(function () {
          var jobs = [];
          if (Array.isArray(data.journal) && data.journal.length) {
            jobs.push(apiFetch('/journal', { method: 'POST', body: { items: data.journal } }));
          }
          if (Array.isArray(data.todos) && data.todos.length) {
            jobs.push(apiFetch('/todos', { method: 'POST', body: { items: data.todos } }));
          }
          return Promise.all(jobs);
        }).then(function () {
          return hydrate();
        }).then(function () {
          if (callback) callback(null, { journal: (data.journal || []).length, todos: (data.todos || []).length });
        }).catch(function (err) { if (callback) callback(err); });
      } catch (err) {
        if (callback) callback(err);
      }
    };
    reader.readAsText(file);
  }

  // ── Inline Modal (unchanged styling) ───────────────────────────────────────
  var modalCSS = [
    '.gs-modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:flex;align-items:center;justify-content:center;padding:16px}',
    '.gs-modal{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;max-width:520px;width:100%;max-height:90vh;overflow-y:auto;font-family:"JetBrains Mono",monospace;color:#f1f5f9;font-size:13px}',
    '.gs-modal h3{font-size:15px;margin-bottom:14px;color:#f1f5f9}',
    '.gs-modal label{display:block;font-size:11px;color:#94a3b8;margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em}',
    '.gs-modal input,.gs-modal textarea,.gs-modal select{width:100%;background:#0f172a;border:1px solid #334155;color:#f1f5f9;font-family:inherit;font-size:12px;padding:8px 10px;border-radius:6px;margin-bottom:12px;resize:vertical}',
    '.gs-modal textarea{min-height:100px}',
    '.gs-modal .gs-modal-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:8px}',
    '.gs-modal button{font-family:inherit;font-size:12px;padding:7px 16px;border-radius:6px;border:1px solid #334155;cursor:pointer;transition:all .15s}',
    '.gs-modal .gs-btn-cancel{background:transparent;color:#94a3b8}',
    '.gs-modal .gs-btn-cancel:hover{color:#f1f5f9;border-color:#94a3b8}',
    '.gs-modal .gs-btn-save{background:#00bbf9;border-color:#00bbf9;color:#000;font-weight:700}',
    '.gs-modal .gs-btn-save:hover{background:#38bdf8}',
    '.gs-modal .gs-modal-link{font-size:11px;color:#94a3b8;margin-top:8px;display:block}',
    '.gs-modal .gs-modal-link:hover{color:#00bbf9}',
    '.gs-modal .gs-activity-info{font-size:11px;color:#94a3b8;background:#0f172a;padding:8px 10px;border-radius:6px;margin-bottom:12px}',
  ].join('\n');

  var styleInjected = false;
  function injectStyle() {
    if (styleInjected) return;
    var s = document.createElement('style');
    s.textContent = modalCSS;
    document.head.appendChild(s);
    styleInjected = true;
  }

  function openJournalModal(opts, callback) {
    injectStyle();
    opts = opts || {};
    var overlay = document.createElement('div');
    overlay.className = 'gs-modal-overlay';
    var actInfo = '';
    if (opts.activity_name || opts.activity_date) {
      actInfo = '<div class="gs-activity-info">Linked: ' + escH(opts.activity_name || '') + (opts.activity_date ? ' (' + escH(opts.activity_date) + ')' : '') + '</div>';
    }
    overlay.innerHTML =
      '<div class="gs-modal">' +
        '<h3>New Journal Entry</h3>' +
        actInfo +
        '<label>Title</label>' +
        '<input type="text" id="gsJTitle" value="' + escH(opts.title || '') + '" placeholder="Entry title..." />' +
        '<label>Body (markdown)</label>' +
        '<textarea id="gsJBody" placeholder="Write your reflection...">' + escH(opts.body || '') + '</textarea>' +
        '<label>Tags (comma-separated)</label>' +
        '<input type="text" id="gsJTags" value="' + escH((opts.tags || []).join(', ')) + '" placeholder="recovery, pacing" />' +
        '<div class="gs-modal-actions">' +
          '<button class="gs-btn-cancel" id="gsJCancel">Cancel</button>' +
          '<button class="gs-btn-save" id="gsJSave">Save</button>' +
        '</div>' +
        '<a href="journal.html" class="gs-modal-link">Open Journal page &rarr;</a>' +
      '</div>';
    document.body.appendChild(overlay);
    overlay.querySelector('#gsJCancel').addEventListener('click', function () { overlay.remove(); });
    overlay.addEventListener('click', function (e) { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#gsJSave').addEventListener('click', function () {
      var title = overlay.querySelector('#gsJTitle').value.trim();
      var body = overlay.querySelector('#gsJBody').value.trim();
      var tagsRaw = overlay.querySelector('#gsJTags').value;
      var tags = tagsRaw ? tagsRaw.split(',').map(function (t) { return t.trim(); }).filter(Boolean) : [];
      if (!title && !body) return;
      var item = Journal.create({
        title: title || 'Untitled', body: body,
        activity_id: opts.activity_id || null, activity_date: opts.activity_date || null,
        activity_name: opts.activity_name || null, tags: tags, source: opts.source || 'manual'
      });
      overlay.remove();
      if (callback) callback(item);
    });
    setTimeout(function () { overlay.querySelector('#gsJTitle').focus(); }, 50);
  }

  function openTodoModal(opts, callback) {
    injectStyle();
    opts = opts || {};
    var overlay = document.createElement('div');
    overlay.className = 'gs-modal-overlay';
    overlay.innerHTML =
      '<div class="gs-modal">' +
        '<h3>New Todo</h3>' +
        '<label>Task</label>' +
        '<input type="text" id="gsTText" value="' + escH(opts.text || '') + '" placeholder="What to do..." />' +
        '<label>Priority</label>' +
        '<select id="gsTPrio">' +
          '<option value="high"' + (opts.priority === 'high' ? ' selected' : '') + '>High</option>' +
          '<option value="medium"' + (opts.priority !== 'high' ? ' selected' : '') + '>Medium</option>' +
          '<option value="low"' + (opts.priority === 'low' ? ' selected' : '') + '>Low</option>' +
        '</select>' +
        '<div class="gs-modal-actions">' +
          '<button class="gs-btn-cancel" id="gsTCancel">Cancel</button>' +
          '<button class="gs-btn-save" id="gsTSave">Save</button>' +
        '</div>' +
        '<a href="todos.html" class="gs-modal-link">Open Todos page &rarr;</a>' +
      '</div>';
    document.body.appendChild(overlay);
    overlay.querySelector('#gsTCancel').addEventListener('click', function () { overlay.remove(); });
    overlay.addEventListener('click', function (e) { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#gsTSave').addEventListener('click', function () {
      var text = overlay.querySelector('#gsTText').value.trim();
      if (!text) return;
      var item = Todo.create({
        text: text, priority: overlay.querySelector('#gsTPrio').value,
        source: opts.source || 'manual', source_detail: opts.source_detail || null
      });
      overlay.remove();
      if (callback) callback(item);
    });
    setTimeout(function () { overlay.querySelector('#gsTText').focus(); }, 50);
  }

  function escH(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── Public API ─────────────────────────────────────────────────────────────
  window.GS = {
    ready: ready,
    Journal: Journal,
    Todo: Todo,
    exportData: exportData,
    importData: importData,
    openJournalModal: openJournalModal,
    openTodoModal: openTodoModal,
    logout: function () { clearToken(); location.reload(); }
  };

})(window);
