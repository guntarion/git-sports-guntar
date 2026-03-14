# 05 — Kerja Solo dari Banyak Komputer

## Pertanyaan Umum

### Pakai satu akun GitHub atau banyak?

**Satu akun saja.** Tidak ada alasan pakai akun berbeda untuk project yang sama. GitHub dirancang untuk multi-device dengan satu akun.

Yang berbeda di setiap komputer hanyalah **metode autentikasi** ke GitHub.

## Setup di Setiap Komputer

### 1. Git Config (per komputer, satu kali)

```bash
git config --global user.name "Nama Kamu"
git config --global user.email "email@example.com"
```

Pakai **email yang sama** di semua komputer supaya commit history konsisten.

### 2. Autentikasi GitHub

**Opsi A: GitHub CLI (Rekomendasi)**
```bash
# Install gh (tersedia di Mac dan Windows)
brew install gh          # Mac
winget install GitHub.cli # Windows

# Login
gh auth login
# Pilih: GitHub.com → HTTPS → Login with browser
```

**Opsi B: SSH Key**
```bash
# Generate SSH key di setiap komputer
ssh-keygen -t ed25519 -C "email@example.com"

# Tambahkan ke GitHub
cat ~/.ssh/id_ed25519.pub
# Copy → GitHub Settings → SSH Keys → New SSH key
```

Setiap komputer punya SSH key sendiri. Tidak perlu copy key antar komputer.

**Opsi C: HTTPS + Credential Manager**
Git Credential Manager (bawaan Git for Windows, atau install di Mac) menyimpan token otomatis.

### 3. Clone Repo

```bash
git clone https://github.com/guntarion/git-sports-guntar.git
```

Cukup sekali per komputer.

## Workflow Harian Multi-Komputer

```
PAGI (Komputer A):
  git pull                    ← Ambil perubahan terbaru
  ... kerja ...
  git add . && git commit     ← Simpan perubahan
  git push                    ← Upload ke GitHub

SORE (Komputer B):
  git pull                    ← Ambil perubahan dari Komputer A
  ... kerja ...
  git add . && git commit
  git push

MALAM (Komputer C):
  git pull                    ← Ambil semua perubahan
  ...
```

**Aturan emas: Selalu `git pull` sebelum mulai kerja.**

## Menghindari Konflik

### Kenapa Konflik Terjadi?

Kalau kamu edit file yang sama di dua komputer **tanpa pull dulu**, git tidak tahu versi mana yang benar.

```
Komputer A: edit line 10 di app.js → push
Komputer B: edit line 10 di app.js → push → CONFLICT!
```

### Cara Menghindari

1. **Selalu pull sebelum kerja** — `git pull` adalah kebiasaan wajib
2. **Selalu push setelah selesai** — Jangan tinggalkan uncommitted changes
3. **Gunakan feature branch** untuk pekerjaan yang belum selesai

### Kalau Terjadi Konflik

```bash
git pull
# Git akan menampilkan: CONFLICT in file.js

# Buka file, cari marker:
# <<<<<<< HEAD
# Versi kamu
# =======
# Versi dari remote
# >>>>>>> origin/main

# Edit file, hapus marker, pilih versi yang benar
git add file.js
git commit -m "resolve merge conflict"
git push
```

## Claude Code di Multi-Komputer

Claude Code menyimpan memory per-project di `~/.claude/projects/`. Memory ini **lokal per komputer** — tidak sync.

Tapi file `.claude/` yang ada di repo (misal `CLAUDE.md`, agent files) tersinkron via git karena ada di repo.

Tips:
- `CLAUDE.md` di root repo → bisa diakses Claude Code di semua komputer
- Memory personal Claude Code → per-komputer saja, tidak masalah

## Mac vs Windows: Perbedaan yang Perlu Diperhatikan

| Aspek | Mac | Windows |
|-------|-----|---------|
| Line ending | LF (`\n`) | CRLF (`\r\n`) |
| Path separator | `/` | `\` |
| Case sensitivity | Default: case-insensitive | Case-insensitive |
| Terminal | Terminal.app / iTerm2 | PowerShell / WSL |

### Setting Penting untuk Cross-Platform

```bash
# Di semua komputer, set ini:
git config --global core.autocrlf input    # Mac/Linux
git config --global core.autocrlf true     # Windows
```

Ini memastikan line ending konsisten di repo (LF) meskipun OS berbeda.

### `.gitattributes` (Rekomendasi)

Tambahkan di root repo:
```
* text=auto
*.sh text eol=lf
*.py text eol=lf
*.js text eol=lf
*.html text eol=lf
*.css text eol=lf
*.yaml text eol=lf
*.json text eol=lf
*.png binary
*.jpg binary
```
