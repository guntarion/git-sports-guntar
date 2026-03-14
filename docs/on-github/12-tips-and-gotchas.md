# 12 — Tips dan Hal yang Perlu Diperhatikan

## Git Gotchas

### 1. Jangan Commit File Besar

Git menyimpan **semua versi** dari setiap file. Kalau kamu commit file 50 MB, bahkan setelah dihapus, repo tetap menyimpannya di history.

```
✅ Kode, config, markdown, JSON kecil
❌ Video, dataset besar, binary, node_modules, .env
```

Pakai `.gitignore` untuk mencegah file yang tidak seharusnya masuk.

### 2. Jangan Commit Secrets

Kalau sudah terlanjur commit password:
1. Ganti password **segera**
2. File masih ada di git history meskipun sudah dihapus
3. Untuk benar-benar menghapus dari history: `git filter-branch` atau BFG Repo Cleaner (advanced)

### 3. `git pull` Sebelum `git push`

Kalau push gagal karena "rejected", itu berarti remote punya commit yang belum kamu punya:
```bash
git pull --rebase    # Lebih bersih daripada git pull biasa
git push
```

### 4. `.gitignore` Hanya Berlaku untuk File Baru

Kalau file sudah ter-track lalu ditambahkan ke `.gitignore`, git tetap track. Untuk untrack:
```bash
git rm --cached nama-file
git commit -m "chore: stop tracking nama-file"
```

## GitHub Actions Gotchas

### 1. Cron Tidak Tepat Waktu

`schedule` cron di Actions bisa delay 5-30 menit. Jangan andalkan untuk timing yang presisi.

### 2. Workflow Hanya Jalan di Default Branch

Kalau buat workflow baru di feature branch, workflow itu **tidak akan jalan** sampai di-merge ke `main` (default branch). Kecuali trigger-nya `push` ke branch itu sendiri.

### 3. Secrets Tidak Tersedia di Fork PR

Kalau seseorang fork repo kamu dan buat PR, workflow yang jalan dari fork mereka **tidak bisa akses secrets** kamu. Ini fitur keamanan.

### 4. Actions Log Otomatis Hapus Setelah 90 Hari

Log workflow run dihapus otomatis setelah 90 hari. Kalau perlu data jangka panjang, simpan di artifact atau commit ke repo.

### 5. GITHUB_TOKEN Permissions

`GITHUB_TOKEN` yang otomatis tersedia di workflow punya permission terbatas. Kalau butuh akses lebih (misal push ke branch lain), perlu set `permissions:` di workflow.

## GitHub Pages Gotchas

### 1. Cache CDN

Setelah deploy, perubahan mungkin tidak langsung terlihat. Browser dan CDN GitHub meng-cache halaman. Solusi:
- Hard refresh: Cmd+Shift+R (Mac) / Ctrl+Shift+R (Windows)
- Tambahkan version query: `app.js?v=abc123` (sudah dilakukan di project ini via `__APP_VERSION__`)

### 2. URL Case-Sensitive

GitHub Pages case-sensitive:
```
/Journal.html  ≠  /journal.html
```
Pastikan link sesuai dengan nama file yang sebenarnya.

### 3. SPA Routing Tidak Didukung

GitHub Pages tidak punya server-side routing. Kalau pakai SPA framework (React Router, Next.js), URL seperti `/dashboard/settings` akan 404.

Workaround: Gunakan hash routing (`/#/dashboard/settings`) atau buat `404.html` yang redirect.

## Tips Umum

### 1. Atomic Commits

Satu commit = satu perubahan logis.

```bash
# Bagus
git commit -m "feat: add journal page"
git commit -m "fix: filter pace > 15:00/km"

# Kurang bagus
git commit -m "banyak perubahan hari ini"
```

### 2. Commit Message Convention

Format: `type: description`

| Type | Kapan |
|------|-------|
| `feat:` | Fitur baru |
| `fix:` | Bug fix |
| `docs:` | Dokumentasi |
| `style:` | Formatting (tidak ubah logika) |
| `refactor:` | Refactor (tidak ubah behavior) |
| `test:` | Tambah/ubah test |
| `chore:` | Maintenance, dependency update |

### 3. `.gitattributes` untuk Cross-Platform

Buat file `.gitattributes` di root:
```
* text=auto
*.sh text eol=lf
*.py text eol=lf
```

Ini mencegah masalah line ending antara Mac dan Windows.

### 4. GitHub CLI (`gh`) Cheat Sheet

```bash
# Repo
gh repo view                    # Info repo
gh repo clone owner/repo        # Clone

# Issues
gh issue create                 # Buat issue
gh issue list                   # List issues
gh issue close 5                # Tutup issue #5

# Pull Requests
gh pr create                    # Buat PR
gh pr list                      # List PRs
gh pr merge                     # Merge PR

# Actions
gh run list                     # List workflow runs
gh run view <id>                # Detail run
gh run watch <id>               # Watch run real-time
gh workflow run "Name"          # Trigger workflow

# Auth
gh auth status                  # Cek login status
gh auth login                   # Login
```

### 5. Kapan Pakai GitHub vs Sistem Lain

| Kebutuhan | GitHub | Alternatif |
|-----------|--------|------------|
| Kode & versioning | Git + GitHub | GitLab, Bitbucket |
| CI/CD | GitHub Actions | GitLab CI, Jenkins, CircleCI |
| Static hosting | GitHub Pages | Vercel, Netlify, Cloudflare Pages |
| Issue tracking | GitHub Issues | Linear, Jira, Notion |
| Project management | GitHub Projects | Linear, Trello, Notion |
| Documentation | Repo markdown | Notion, Confluence |

Untuk developer solo, **GitHub saja sudah cukup** untuk hampir semua kebutuhan. Tambahkan tool lain hanya kalau ada kebutuhan spesifik.
