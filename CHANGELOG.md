## 2026-03-16 08:27:41

feat: add running data export (JSON/CSV) for AI analysis

- Export bar on Activities page with count selector (1, 5, 10, 20)
- JSON format with metadata, units, HR zones, and per-km splits
- CSV format with flat summary + separate splits detail section
- Filtered to running activities only, sorted newest first
- AI-friendly field names and raw numeric values preserved

---

## 2026-03-15 02:45:57

docs: add GitHub guide series for solo developers

- 13 numbered markdown files in docs/on-github/
- Covers Actions, Pages, Secrets, Branches, multi-machine workflow,
  Issues & Projects, Pull Requests, Security, Claude Code integration,
  GitHub Pages limitations, useful Actions from marketplace, and tips

---

## 2026-03-14 21:12:18

docs: add Journal & Todos documentation and screenshots

- Create docs/journal-todos.md with architecture, data schema, and API reference
- Add Journal and Todos screenshots to docs/
- Update README.md with Journal & Todos feature section and screenshots
- Update Dashboard Pages table with Journal and Todos entries

---

## 2026-03-14 20:02:01

feat: add Journal & Todo List with localStorage persistence

- Create storage.js shared module (CRUD, inline modal, export/import)
- Create journal.html with markdown editor/preview (marked.js + DOMPurify)
- Create todos.html with quick add, filters, and bulk actions
- Add action buttons on AI recommendations in analytics.html (save to journal/todo)
- Add "Add Note" button on hero card in records.html (linked to activity)
- Add Journal and Todos nav links to all existing pages

---

