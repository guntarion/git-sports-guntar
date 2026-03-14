# 00 — Overview: Apa Itu GitHub Sebenarnya?

## Bukan Sekadar Tempat Taruh Kode

GitHub adalah **platform** yang menyediakan:

1. **Git hosting** — Tempat menyimpan repository (kode + history)
2. **Actions** — Server gratis yang menjalankan kode otomatis (CI/CD)
3. **Pages** — Hosting website statis gratis
4. **Issues & Projects** — Manajemen tugas dan bug tracking
5. **Pull Requests** — Review dan merge perubahan kode
6. **Security** — Secret management, dependency scanning, vulnerability alerts
7. **Codespaces** — IDE berbasis cloud (VS Code di browser)

## Apa yang Kita Lakukan di Project Ini

```
┌──────────────────────────────────────────────────────────────┐
│                        GITHUB                                │
│                                                              │
│  ┌─── Repository (main branch) ───────────────────────┐     │
│  │  Kode Python, HTML, CSS, JS, workflow YAML          │     │
│  │  Push dari komputer lokal → trigger Actions & Pages │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌─── Actions (Sync Heatmaps) ────────────────────────┐     │
│  │  Jalan setiap hari 15:00 UTC                        │     │
│  │  Server Ubuntu gratis, install Python, jalankan ETL │     │
│  │  Simpan hasil di branch dashboard-data              │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌─── Actions (Deploy Pages) ─────────────────────────┐     │
│  │  Otomatis jalan setelah Sync selesai                │     │
│  │  Ambil HTML dari main + data dari dashboard-data    │     │
│  │  Deploy ke GitHub Pages                             │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌─── Pages ──────────────────────────────────────────┐     │
│  │  https://guntarion.github.io/git-sports-guntar/     │     │
│  │  Hosting statis gratis, HTTPS otomatis              │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌─── Secrets & Variables ────────────────────────────┐     │
│  │  GARMIN_EMAIL, GARMIN_PASSWORD, QWEN_API_KEY       │     │
│  │  Disimpan terenkripsi, hanya bisa diakses Actions   │     │
│  └─────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

## Daftar Dokumen

| File | Topik |
|------|-------|
| [01-actions-workflows.md](01-actions-workflows.md) | GitHub Actions & Workflows |
| [02-pages.md](02-pages.md) | GitHub Pages (static hosting) |
| [03-secrets-variables.md](03-secrets-variables.md) | Secrets, Variables, dan Environment |
| [04-branches-strategy.md](04-branches-strategy.md) | Branching dan cara kerja multi-branch |
| [05-solo-dev-multi-machine.md](05-solo-dev-multi-machine.md) | Kerja solo dari banyak komputer |
| [06-issues-projects.md](06-issues-projects.md) | Issues, Projects, dan task management |
| [07-pull-requests.md](07-pull-requests.md) | Pull Requests untuk developer solo |
| [08-security-settings.md](08-security-settings.md) | Security settings dan rekomendasi |
| [09-claude-code-on-github.md](09-claude-code-on-github.md) | Menggunakan Claude Code dengan GitHub |
| [10-limitations-and-beyond.md](10-limitations-and-beyond.md) | Batasan GitHub Pages dan opsi upgrade |
| [11-useful-actions.md](11-useful-actions.md) | Actions marketplace: linting, testing, dll |
| [12-tips-and-gotchas.md](12-tips-and-gotchas.md) | Tips dan hal-hal yang perlu diperhatikan |
