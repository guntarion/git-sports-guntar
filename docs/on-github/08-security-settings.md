# 08 — Security Settings dan Rekomendasi

## Security Overview di Repo Kamu

Berdasarkan screenshot, status security repo kamu saat ini:

| Fitur | Status | Rekomendasi |
|-------|--------|-------------|
| Security policy | Disabled | Opsional untuk project personal |
| Security advisories | Enabled | Bagus, biarkan on |
| Private vulnerability reporting | Disabled | Opsional |
| Dependabot alerts | **Disabled** | **Sebaiknya enable** |
| Code scanning | Needs setup | Opsional |
| Secret scanning | Enabled | Bagus, biarkan on |

## Fitur Security yang Perlu Diketahui

### 1. Secret Scanning (Sudah Aktif)

GitHub otomatis scan setiap push untuk pattern yang terlihat seperti secret (API key, password, token). Kalau terdeteksi, kamu dapat alert.

**Penting**: Ini scan pattern yang dikenal (AWS key, GitHub token, dll). Tidak semua format terdeteksi. Jadi tetap hati-hati.

### 2. Dependabot Alerts (Rekomendasi: Enable)

Dependabot memantau dependencies kamu dan memberi alert kalau ada vulnerability.

Cara enable:
Settings → Code security and analysis → Dependabot alerts → Enable

Untuk project Python, Dependabot baca `requirements.txt` dan kasih tahu kalau ada library yang punya CVE (security vulnerability).

### 3. Dependabot Security Updates (Opsional)

Kalau di-enable, Dependabot otomatis buat PR untuk update library yang vulnerable:

```
Dependabot: Bump requests from 2.28.0 to 2.31.0
(fixes CVE-2023-xxxxx)
```

### 4. Code Scanning (Opsional)

Pakai CodeQL untuk analisis statik — deteksi bug dan vulnerability di kode. Berguna untuk project yang lebih besar.

### 5. Branch Protection Rules

Settings → Branches → Add rule

| Rule | Artinya |
|------|---------|
| Require PR | Push langsung ke main diblokir |
| Require status checks | CI harus pass sebelum merge |
| Require signed commits | Commit harus cryptographically signed |
| Restrict push | Hanya user tertentu yang bisa push |

Untuk solo developer, ini biasanya **tidak perlu**. Tapi kalau mau extra safety (mencegah push tidak sengaja ke main), bisa enable "Require PR".

## Settings Penting Lainnya

### General Settings

Settings → General:

| Setting | Rekomendasi |
|---------|-------------|
| Default branch | `main` |
| Features: Issues | On |
| Features: Projects | On (kalau dipakai) |
| Features: Wiki | Off (pakai docs/ folder saja) |
| Merge button | Allow merge commits + Allow squash merging |

### Actions Settings

Settings → Actions → General:

| Setting | Rekomendasi |
|---------|-------------|
| Actions permissions | Allow all actions |
| Workflow permissions | Read and write permissions |
| Allow GitHub Actions to create PRs | On (kalau pakai Dependabot) |

### Pages Settings

Settings → Pages:

| Setting | Rekomendasi |
|---------|-------------|
| Source | GitHub Actions |
| Custom domain | Opsional |
| Enforce HTTPS | On |

## Checklist Security untuk Project Ini

- [x] Secret scanning enabled
- [ ] Enable Dependabot alerts
- [x] Secrets (GARMIN password, API keys) di repo Secrets, bukan di kode
- [x] `config.local.yaml` di `.gitignore`
- [x] Workflow permissions minimal (hanya `contents: write` dan `pages: write`)
- [x] Concurrency group mencegah parallel execution
