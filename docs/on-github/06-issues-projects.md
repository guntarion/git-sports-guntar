# 06 — Issues, Projects, dan Task Management

## GitHub Issues

Issues adalah **ticket system** bawaan GitHub. Setiap issue punya:
- Judul dan deskripsi (markdown)
- Label (misal: `bug`, `enhancement`, `question`)
- Assignee (siapa yang mengerjakan)
- Milestone (target rilis)
- Linked PR (pull request yang menyelesaikan issue)

### Cara Pakai untuk Developer Solo

Meskipun sendirian, Issues tetap berguna sebagai **to-do list yang persistent**:

```bash
# Buat issue dari CLI
gh issue create --title "Tambah export CSV di records page" --label "enhancement"

# List issues
gh issue list

# Tutup issue
gh issue close 5

# Lihat detail
gh issue view 5
```

### Contoh Use Case

| Issue | Label | Artinya |
|-------|-------|---------|
| "Pace filter > 15:00/km masih muncul" | `bug` | Bug yang perlu diperbaiki |
| "Tambah dark/light mode toggle" | `enhancement` | Fitur baru |
| "Investigate Garmin API rate limit" | `research` | Perlu riset |
| "Upgrade Chart.js ke v5" | `chore` | Maintenance |

### Tips: Close Issue via Commit

Tulis keyword di commit message:

```bash
git commit -m "fix: filter pace > 15:00/km — closes #5"
```

Keyword yang dikenali: `closes`, `fixes`, `resolves` + `#nomor`

Issue #5 akan otomatis tertutup saat commit ini masuk ke main.

## GitHub Projects

Projects adalah **Kanban board** (seperti Trello) bawaan GitHub.

### Apa yang Bisa Dilakukan

- Board view: kolom "To Do", "In Progress", "Done"
- Table view: spreadsheet-style dengan custom fields
- Otomatis link ke Issues dan PRs
- Custom fields: priority, effort, sprint, dll
- Automasi: auto-move card saat issue closed

### Cara Membuat

1. Tab **Projects** di repo → **New project**
2. Pilih template (Board, Table, atau Roadmap)
3. Tambahkan items (Issues yang sudah ada atau draft item baru)

### Apakah Perlu untuk Solo Developer?

**Opsional tapi berguna** kalau:
- Project mulai besar (banyak fitur yang ingin ditrack)
- Kamu ingin visual overview dari semua pekerjaan
- Kamu kerja di beberapa project GitHub dan ingin satu tempat untuk melihat semua

Kalau project masih kecil, cukup Issues saja tanpa Projects.

### Contoh Setup Board

```
┌─────────────┬──────────────┬─────────────┐
│   Backlog   │  In Progress │    Done     │
├─────────────┼──────────────┼─────────────┤
│ Export CSV  │ Journal page │ AI Coach    │
│ Z2 filter  │              │ Records     │
│ Mobile fix  │              │ Activities  │
│             │              │ Heatmap     │
└─────────────┴──────────────┴─────────────┘
```

## Milestones

Milestone = target rilis. Group beberapa issues ke satu milestone:

```bash
# Buat milestone
gh api repos/{owner}/{repo}/milestones --method POST \
  -f title="v2.0" -f description="Journal, Todo, Export" -f due_on="2026-04-01T00:00:00Z"
```

Berguna kalau kamu punya "version" atau "release" yang jelas.

## Labels

Buat label custom sesuai kebutuhan:

```bash
gh label create "ai-coach" --color "a78bfa" --description "Related to AI Coach feature"
gh label create "frontend" --color "00bbf9" --description "HTML/CSS/JS changes"
gh label create "pipeline" --color "f97316" --description "Python ETL pipeline"
```

## Rekomendasi untuk Solo Developer

1. **Minimal**: Pakai Issues sebagai to-do list. Tulis ide dan bug di sana supaya tidak lupa.
2. **Medium**: Pakai Issues + Labels. Categorize pekerjaan.
3. **Full**: Pakai Issues + Projects board. Track progress visual.

Jangan over-engineer. Kalau cukup dengan catatan di Notes app, itu juga tidak masalah. Tools ini ada untuk membantu, bukan menambah beban.
