# 01 — GitHub Actions & Workflows

## Apa Itu GitHub Actions?

GitHub Actions adalah **server gratis** yang menjalankan kode kamu secara otomatis. Bayangkan punya komputer Ubuntu di cloud yang bisa kamu suruh:
- Jalankan script Python setiap hari jam 3 sore
- Test kode setiap kali ada push
- Deploy website otomatis
- Dan banyak lagi

## Anatomi Workflow File

Workflow didefinisikan di file YAML di `.github/workflows/`. Project ini punya 2 workflow:

### 1. `sync.yml` — Sync Heatmaps

```yaml
name: Sync Heatmaps

on:
  schedule:
    - cron: "0 15 * * *"        # Jalan setiap hari jam 15:00 UTC
  workflow_dispatch:             # Bisa juga di-trigger manual
    inputs:
      source:                    # Parameter yang bisa dipilih saat manual trigger
        type: choice
        options: [strava, garmin]
```

**Apa yang dilakukan:**
1. Checkout kode dari repo
2. Install Python 3.11 dan dependencies
3. Buat `config.local.yaml` dari Secrets
4. Ambil data persisted dari branch `dashboard-data`
5. Jalankan `run_pipeline.py` (ETL: sync → enrich → normalize → generate)
6. Push hasil ke branch `dashboard-data`

### 2. `pages.yml` — Deploy Pages

```yaml
on:
  push:
    branches: [main]
    paths: [site/**]              # Hanya jalan kalau file di site/ berubah
  workflow_run:
    workflows: [Sync Heatmaps]   # Jalan otomatis setelah Sync selesai
    types: [completed]
```

**Apa yang dilakukan:**
1. Checkout kode dari `main`
2. Ambil `data.json`, `activities.json`, `ai_insights.json` dari branch `dashboard-data`
3. Upload folder `site/` sebagai artifact
4. Deploy ke GitHub Pages

## Konsep Penting

### Triggers (`on:`)

| Trigger | Artinya | Contoh |
|---------|---------|--------|
| `push` | Saat push ke branch tertentu | Deploy saat push ke main |
| `schedule` | Cron job terjadwal | Sync data setiap hari |
| `workflow_dispatch` | Trigger manual dari UI/CLI | Tombol "Run workflow" |
| `workflow_run` | Setelah workflow lain selesai | Deploy setelah Sync |
| `pull_request` | Saat PR dibuat/diupdate | Jalankan test |

### Cron Syntax

```
┌───────────── menit (0-59)
│ ┌───────────── jam (0-23, UTC!)
│ │ ┌───────────── tanggal (1-31)
│ │ │ ┌───────────── bulan (1-12)
│ │ │ │ ┌───────────── hari (0-6, 0=Minggu)
│ │ │ │ │
0 15 * * *    → Setiap hari jam 15:00 UTC (22:00 WIB)
```

Catatan: GitHub **tidak menjamin** jadwal persis. Bisa delay 5-30 menit saat server sibuk.

### Steps dan Actions

Setiap job berisi steps. Step bisa berupa:

```yaml
steps:
  # Pakai action dari marketplace
  - uses: actions/checkout@v4

  # Jalankan command shell
  - run: pip install -r requirements.txt

  # Dengan nama dan kondisi
  - name: Deploy
    if: ${{ success() }}
    run: echo "Done!"
```

### Secrets dalam Workflow

```yaml
env:
  GARMIN_EMAIL: ${{ secrets.GARMIN_EMAIL }}     # Dari repo Secrets
  DASHBOARD_SOURCE: ${{ vars.DASHBOARD_SOURCE }} # Dari repo Variables
```

- `secrets.*` — Terenkripsi, tidak pernah muncul di log
- `vars.*` — Plaintext, muncul di log (untuk config non-sensitif)

### Concurrency

```yaml
concurrency:
  group: sync-${{ github.repository }}
  cancel-in-progress: false    # Jangan cancel yang sedang jalan
```

Ini mencegah dua sync jalan bersamaan (bisa corrupt data).

## Cara Trigger Manual

### Dari GitHub UI
Actions → Sync Heatmaps → Run workflow → Pilih parameter → Klik

### Dari CLI (`gh`)
```bash
gh workflow run "Sync Heatmaps" --field source=garmin
gh workflow run "Sync Heatmaps" --field source=garmin --field full_backfill=true
```

### Dari Claude Code
```bash
# Langsung dari terminal Claude Code
gh workflow run "Sync Heatmaps" --field source=garmin
```

## Batasan Free Tier

| Resource | Limit |
|----------|-------|
| Runtime | 2.000 menit/bulan (repo publik: unlimited) |
| Storage | 500 MB artifact storage |
| Concurrent jobs | 20 |
| Job timeout | Maks 6 jam per job |
| Cron minimal | Setiap 5 menit (tapi delay bisa 15-30 menit) |

Project ini menggunakan ~2-5 menit per sync, jadi ~60-150 menit/bulan. Sangat aman.

## Melihat Log dan Debug

1. **Actions tab** → Klik workflow run → Klik job → Expand step
2. Setiap step menampilkan output stdout/stderr
3. Secrets otomatis di-mask (muncul sebagai `***`)
4. Kalau gagal, lihat step merah untuk error message

## Workflow Artifacts

Workflow bisa menyimpan file output (artifact):
```yaml
- uses: actions/upload-pages-artifact@v3
  with:
    path: site    # Upload seluruh folder site/
```

Artifact bisa didownload dari Actions tab, berguna untuk debug.
