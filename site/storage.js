/* storage.js — Shared localStorage CRUD, modal helper, export/import
 * Used by: journal.html, todos.html, analytics.html, records.html
 */
(function (window) {
  'use strict';

  var JOURNAL_KEY = 'gitsweaty_journal';
  var TODOS_KEY = 'gitsweaty_todos';

  // ── ID generation ──────────────────────────────────────────────────────────
  function genId(prefix) {
    var ts = Date.now();
    var rand = Math.random().toString(16).slice(2, 6);
    return prefix + '_' + ts + '_' + rand;
  }

  // ── Safe JSON read/write ───────────────────────────────────────────────────
  function readStore(key) {
    try {
      return JSON.parse(localStorage.getItem(key)) || [];
    } catch (e) {
      return [];
    }
  }
  function writeStore(key, data) {
    try {
      localStorage.setItem(key, JSON.stringify(data));
      return true;
    } catch (e) {
      return false;
    }
  }

  // ── Journal CRUD ───────────────────────────────────────────────────────────
  var Journal = {
    getAll: function () { return readStore(JOURNAL_KEY); },
    getById: function (id) { return this.getAll().find(function (j) { return j.id === id; }) || null; },
    create: function (entry) {
      var now = new Date().toISOString();
      var item = {
        id: genId('j'),
        created_at: now,
        updated_at: now,
        title: entry.title || '',
        body: entry.body || '',
        activity_id: entry.activity_id || null,
        activity_date: entry.activity_date || null,
        activity_name: entry.activity_name || null,
        tags: entry.tags || [],
        source: entry.source || 'manual'
      };
      var all = this.getAll();
      all.unshift(item);
      writeStore(JOURNAL_KEY, all);
      return item;
    },
    update: function (id, changes) {
      var all = this.getAll();
      var idx = all.findIndex(function (j) { return j.id === id; });
      if (idx === -1) return null;
      Object.keys(changes).forEach(function (k) { all[idx][k] = changes[k]; });
      all[idx].updated_at = new Date().toISOString();
      writeStore(JOURNAL_KEY, all);
      return all[idx];
    },
    remove: function (id) {
      var all = this.getAll().filter(function (j) { return j.id !== id; });
      writeStore(JOURNAL_KEY, all);
    }
  };

  // ── Todo CRUD ──────────────────────────────────────────────────────────────
  var Todo = {
    getAll: function () { return readStore(TODOS_KEY); },
    getById: function (id) { return this.getAll().find(function (t) { return t.id === id; }) || null; },
    create: function (entry) {
      var now = new Date().toISOString();
      var item = {
        id: genId('t'),
        created_at: now,
        updated_at: now,
        text: entry.text || '',
        done: false,
        done_at: null,
        priority: entry.priority || 'medium',
        due_date: entry.due_date || null,
        source: entry.source || 'manual',
        source_detail: entry.source_detail || null
      };
      var all = this.getAll();
      all.unshift(item);
      writeStore(TODOS_KEY, all);
      return item;
    },
    update: function (id, changes) {
      var all = this.getAll();
      var idx = all.findIndex(function (t) { return t.id === id; });
      if (idx === -1) return null;
      Object.keys(changes).forEach(function (k) { all[idx][k] = changes[k]; });
      all[idx].updated_at = new Date().toISOString();
      writeStore(TODOS_KEY, all);
      return all[idx];
    },
    toggle: function (id) {
      var all = this.getAll();
      var idx = all.findIndex(function (t) { return t.id === id; });
      if (idx === -1) return null;
      all[idx].done = !all[idx].done;
      all[idx].done_at = all[idx].done ? new Date().toISOString() : null;
      all[idx].updated_at = new Date().toISOString();
      writeStore(TODOS_KEY, all);
      return all[idx];
    },
    remove: function (id) {
      var all = this.getAll().filter(function (t) { return t.id !== id; });
      writeStore(TODOS_KEY, all);
    },
    clearCompleted: function () {
      var all = this.getAll().filter(function (t) { return !t.done; });
      writeStore(TODOS_KEY, all);
    }
  };

  // ── Export / Import ────────────────────────────────────────────────────────
  function exportData() {
    var blob = new Blob([JSON.stringify({
      journal: Journal.getAll(),
      todos: Todo.getAll(),
      exported_at: new Date().toISOString()
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
        var jCount = 0, tCount = 0;
        if (data.journal && Array.isArray(data.journal)) {
          var existing = Journal.getAll();
          var ids = {};
          existing.forEach(function (j) { ids[j.id] = true; });
          data.journal.forEach(function (j) {
            if (j.id && !ids[j.id]) { existing.push(j); jCount++; }
          });
          existing.sort(function (a, b) { return b.created_at < a.created_at ? -1 : 1; });
          writeStore(JOURNAL_KEY, existing);
        }
        if (data.todos && Array.isArray(data.todos)) {
          var existing2 = Todo.getAll();
          var ids2 = {};
          existing2.forEach(function (t) { ids2[t.id] = true; });
          data.todos.forEach(function (t) {
            if (t.id && !ids2[t.id]) { existing2.push(t); tCount++; }
          });
          existing2.sort(function (a, b) { return b.created_at < a.created_at ? -1 : 1; });
          writeStore(TODOS_KEY, existing2);
        }
        if (callback) callback(null, { journal: jCount, todos: tCount });
      } catch (err) {
        if (callback) callback(err);
      }
    };
    reader.readAsText(file);
  }

  // ── Inline Modal ───────────────────────────────────────────────────────────
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
        title: title || 'Untitled',
        body: body,
        activity_id: opts.activity_id || null,
        activity_date: opts.activity_date || null,
        activity_name: opts.activity_name || null,
        tags: tags,
        source: opts.source || 'manual'
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
        text: text,
        priority: overlay.querySelector('#gsTPrio').value,
        source: opts.source || 'manual',
        source_detail: opts.source_detail || null
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
    Journal: Journal,
    Todo: Todo,
    exportData: exportData,
    importData: importData,
    openJournalModal: openJournalModal,
    openTodoModal: openTodoModal
  };

})(window);
