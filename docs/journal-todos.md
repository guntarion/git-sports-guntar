# Journal & Todo List

## Overview

Journal dan Todo List adalah fitur browser-side yang memungkinkan user menangkap rekomendasi AI Coach sebagai catatan (journal) atau action item (todo), serta menulis refleksi terkait sesi latihan tertentu.

Semua data disimpan di **localStorage** browser — tidak ada backend atau database yang terlibat.

## Architecture

```
storage.js (shared module, loaded by all pages)
  ├── Journal CRUD → localStorage key: 'gitsweaty_journal'
  ├── Todo CRUD    → localStorage key: 'gitsweaty_todos'
  ├── Inline modal helper (create from any page)
  └── Export/Import (JSON backup/restore)

journal.html ─── Full journal browser + markdown editor
todos.html ───── Todo list with quick add + filters

analytics.html ── [📓][☐] buttons on AI recommendations
records.html ──── [📓 Add Note] button on hero card
```

## Data Schema

### Journal Entry (`gitsweaty_journal`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique ID (`j_{timestamp}_{random}`) |
| `created_at` | ISO string | Creation timestamp |
| `updated_at` | ISO string | Last update timestamp |
| `title` | string | Entry title |
| `body` | string | Body text (markdown supported) |
| `activity_id` | string/null | Linked Garmin activity ID |
| `activity_date` | string/null | Linked activity date |
| `activity_name` | string/null | Linked activity name |
| `tags` | string[] | User-defined tags |
| `source` | string | Origin: `manual`, `ai_rec` |

### Todo Item (`gitsweaty_todos`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique ID (`t_{timestamp}_{random}`) |
| `created_at` | ISO string | Creation timestamp |
| `updated_at` | ISO string | Last update timestamp |
| `text` | string | Task description |
| `done` | boolean | Completion status |
| `done_at` | ISO string/null | Completion timestamp |
| `priority` | string | `high`, `medium`, `low` |
| `due_date` | string/null | Optional due date |
| `source` | string | Origin: `manual`, `ai_rec` |
| `source_detail` | string/null | Extra context (e.g. "Coach recommendation from 2026-03-14") |

## Pages

### Journal (`journal.html`)

- **Search**: Filter entries by title, body, or activity name
- **Tag filter**: Click tag pills to filter by tag
- **Inline editor**: Title, markdown body, tag input, preview toggle
- **Markdown preview**: Rendered via `marked.js`, sanitized with `DOMPurify`
- **CRUD**: Create, edit, delete entries
- **Export/Import**: JSON backup and restore

### Todos (`todos.html`)

- **Quick add**: Always-visible input + priority selector
- **Filters**: All / Active / Completed with live counts
- **Toggle**: Click checkbox to mark done/undone
- **Clear completed**: Bulk remove finished items
- **Export/Import**: JSON backup and restore

## Cross-Page Integration

### From Analytics (AI Recommendations)

Each AI insight and recommendation has action buttons:
- **📓** (Journal) — Opens inline modal pre-filled with the insight/recommendation text
- **☐** (Todo) — Instantly saves the recommendation as a todo item

### From Records (Hero Card)

The hero card showing the latest/selected run has an **📓 Add Note** button that opens the journal modal with the activity pre-linked (ID, date, name).

## Shared Module: `storage.js`

Exposes `window.GS` with:

```javascript
GS.Journal.getAll()        // → array of journal entries
GS.Journal.getById(id)     // → single entry or null
GS.Journal.create(entry)   // → created entry
GS.Journal.update(id, obj) // → updated entry
GS.Journal.remove(id)      // → void

GS.Todo.getAll()           // → array of todo items
GS.Todo.getById(id)        // → single item or null
GS.Todo.create(entry)      // → created item
GS.Todo.toggle(id)         // → toggled item
GS.Todo.update(id, obj)    // → updated item
GS.Todo.remove(id)         // → void
GS.Todo.clearCompleted()   // → void

GS.exportData()            // → triggers JSON file download
GS.importData(file, cb)    // → merges imported data (deduplicates by ID)

GS.openJournalModal(opts, callback) // → opens inline modal
GS.openTodoModal(opts, callback)    // → opens inline modal
```

## Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Device-bound | Data stays in one browser | Export/Import JSON |
| ~5-10 MB limit | Sufficient for hundreds of entries | Monitor usage |
| Can be cleared | Browser data wipe loses everything | Regular export backups |
| No sync | No cloud backup | Manual export to file |

## CDN Dependencies

- `marked.js` v12.0.0 — Markdown → HTML rendering (journal.html only)
- `DOMPurify` v3.0.8 — HTML sanitization for XSS protection (journal.html only)
