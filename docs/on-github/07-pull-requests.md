# 07 — Pull Requests untuk Developer Solo

## Apa Itu Pull Request (PR)?

PR adalah mekanisme untuk **mengusulkan perubahan** dari satu branch ke branch lain. Di tim, PR dipakai untuk code review. Untuk developer solo, PR masih berguna.

## Kenapa Solo Developer Butuh PR?

### 1. Self-Review

Sebelum merge ke main, PR memaksa kamu **melihat semua perubahan** dalam satu tampilan yang rapi. Sering kali kamu menemukan bug atau file yang tidak sengaja ikut.

### 2. Dokumentasi Perubahan

PR menyimpan:
- Deskripsi perubahan
- Semua commit yang terlibat
- Diff lengkap
- Komentar dan diskusi

Ini berguna 6 bulan kemudian saat bertanya "kenapa saya mengubah ini?"

### 3. CI/CD Check

Kalau kamu setup Actions untuk test, PR bisa menjalankan test sebelum merge.

### 4. Claude Code Integration

Claude Code bisa membuat PR otomatis:
```bash
# Dari Claude Code, setelah selesai coding:
gh pr create --title "feat: add journal page" --body "..."
```

## Cara Pakai PR (Solo)

### Alur Sederhana

```bash
# 1. Buat branch
git checkout -b feat/new-page

# 2. Kerja dan commit
git add .
git commit -m "feat: add new page"
git push -u origin feat/new-page

# 3. Buat PR
gh pr create --title "feat: add new page" --body "Added journal page with markdown editor"

# 4. Review sendiri di GitHub (lihat diff, pastikan ok)

# 5. Merge
gh pr merge --merge

# 6. Kembali ke main
git checkout main
git pull
```

### Atau: Push Langsung ke Main

Kalau perubahan kecil dan kamu yakin, push langsung ke main juga **totally fine** untuk solo developer. Tidak ada aturan yang memaksa harus pakai PR.

```bash
git add .
git commit -m "fix: typo in analytics page"
git push
```

## Merge Strategies

| Strategy | Apa yang terjadi | Kapan pakai |
|----------|------------------|-------------|
| Merge commit | Buat commit merge, history semua commit tetap ada | Default, paling aman |
| Squash and merge | Gabungkan semua commit jadi satu | Kalau commit history PR berantakan |
| Rebase and merge | Replay commit di atas main | History linear, tapi lebih advanced |

Untuk solo developer, **merge commit** atau **squash** sudah cukup.

## PR Templates (Opsional)

Buat file `.github/pull_request_template.md`:

```markdown
## Summary
<!-- Apa yang berubah dan kenapa -->

## Test Plan
- [ ] Tested locally
- [ ] Checked on mobile viewport

## Screenshots
<!-- Kalau ada perubahan visual -->
```

Setiap PR baru akan otomatis terisi template ini.

## Auto-Merge (Opsional)

Kalau kamu setup required status checks (misal test harus pass), kamu bisa enable auto-merge:

```bash
gh pr merge --auto --merge
```

PR akan otomatis merge begitu semua check pass.
