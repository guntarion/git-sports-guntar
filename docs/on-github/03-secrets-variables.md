# 03 — Secrets, Variables, dan Environment

## Secrets vs Variables

| | Secrets | Variables |
|---|---------|-----------|
| Enkripsi | Ya (terenkripsi saat disimpan) | Tidak |
| Muncul di log | Tidak (di-mask `***`) | Ya |
| Akses | Hanya di Actions runner | Hanya di Actions runner |
| Guna | Password, API key, token | Config non-sensitif |

## Cara Mengatur

### Via GitHub UI

Settings → Secrets and variables → Actions

Tab **Secrets**: Klik "New repository secret"
Tab **Variables**: Klik "New repository variable"

### Via CLI (`gh`)

```bash
# Set secret
gh secret set GARMIN_EMAIL --body "email@example.com"

# Set variable
gh variable set DASHBOARD_SOURCE --body "garmin"

# List
gh secret list
gh variable list
```

## Secrets di Project Ini

| Secret | Kegunaan | Required? |
|--------|----------|-----------|
| `GARMIN_EMAIL` | Login Garmin Connect | Ya (salah satu) |
| `GARMIN_PASSWORD` | Password Garmin | Ya (salah satu) |
| `GARMIN_TOKENS_B64` | Token OAuth Garmin (alternatif) | Ya (salah satu) |
| `QWEN_API_KEY` | API key untuk AI Coach | Opsional |
| `DATABASE_URL` | PostgreSQL connection string | Opsional |

## Variables di Project Ini

| Variable | Kegunaan | Default |
|----------|----------|---------|
| `DASHBOARD_SOURCE` | `garmin` atau `strava` | `strava` |
| `DASHBOARD_DISTANCE_UNIT` | `km` atau `mi` | `km` |
| `DASHBOARD_ELEVATION_UNIT` | `m` atau `ft` | `m` |
| `DASHBOARD_WEEK_START` | `sunday` atau `monday` | `sunday` |
| `DASHBOARD_REPO` | Slug repo (otomatis) | — |

## Cara Dipakai di Workflow

```yaml
steps:
  - name: Run pipeline
    env:
      # Secret → env variable di runner
      GARMIN_EMAIL: ${{ secrets.GARMIN_EMAIL }}
      QWEN_API_KEY: ${{ secrets.QWEN_API_KEY }}
      # Variable → env variable di runner
      DASHBOARD_SOURCE: ${{ vars.DASHBOARD_SOURCE }}
    run: python scripts/run_pipeline.py
```

Python script mengakses via `os.environ`:
```python
import os
email = os.environ.get('GARMIN_EMAIL')
api_key = os.environ.get('QWEN_API_KEY')
```

## Environment Secrets (Level Lebih Tinggi)

GitHub juga punya **Environments** (Settings → Environments), berguna kalau punya multiple deployment target:
- `production` — secrets untuk deploy production
- `staging` — secrets berbeda untuk staging

Untuk project solo, biasanya cukup pakai repository-level secrets saja.

## Keamanan Penting

1. **Jangan pernah commit secret ke kode** — Kalau tidak sengaja push password, segera rotate (ganti password). Git history menyimpan selamanya.
2. **`.gitignore`** — Pastikan `config.local.yaml` dan file berisi secret ada di `.gitignore`
3. **Fork risk** — Kalau repo public dan ada yang fork, mereka TIDAK bisa akses secret kamu. Tapi kalau mereka submit PR, workflow dari fork mereka juga tidak bisa akses.
4. **Log masking** — GitHub otomatis mask secret di log. Tapi hati-hati kalau secret muncul dalam format yang berbeda (misal base64-encode dari secret).
