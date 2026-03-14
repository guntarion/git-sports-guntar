# 11 — GitHub Actions Marketplace: Yang Berguna

## Actions Marketplace

GitHub Actions punya marketplace berisi ribuan action siap pakai. Kamu tinggal pakai dengan `uses:` di workflow.

## Actions yang Sudah Dipakai di Project Ini

| Action | Versi | Fungsi |
|--------|-------|--------|
| `actions/checkout@v4` | v4 | Checkout kode dari repo |
| `actions/setup-python@v5` | v5 | Install Python versi tertentu |
| `actions/configure-pages@v5` | v5 | Configure GitHub Pages |
| `actions/upload-pages-artifact@v3` | v3 | Upload folder untuk deploy |
| `actions/deploy-pages@v4` | v4 | Deploy ke GitHub Pages |

## Actions yang Berguna untuk Project Python

### Linting & Formatting

```yaml
# Cek kode Python dengan ruff (linter modern, sangat cepat)
- name: Lint with ruff
  uses: chartboost/ruff-action@v1
  with:
    args: check --select E,F,W
```

```yaml
# Cek formatting dengan black
- name: Check formatting
  run: |
    pip install black
    black --check scripts/
```

### Testing

```yaml
# Jalankan pytest
- name: Run tests
  run: |
    pip install pytest
    cd scripts && python -m pytest ../tests/ -v
```

### Dependency Caching

```yaml
# Cache pip dependencies (supaya install lebih cepat)
- uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'    # Otomatis cache berdasarkan requirements.txt
```

## Actions untuk Project JavaScript/Next.js

### Linting

```yaml
- name: Lint
  run: |
    npm ci
    npm run lint
```

### Build Check

```yaml
- name: Build
  run: |
    npm ci
    npm run build
```

### Lighthouse CI (Performance Audit)

```yaml
- uses: treosh/lighthouse-ci-action@v11
  with:
    urls: |
      https://guntarion.github.io/git-sports-guntar/
    uploadArtifacts: true
```

## Actions untuk Otomasi Umum

### Scheduled Tasks (Cron)

```yaml
# Contoh: cleanup setiap minggu
on:
  schedule:
    - cron: '0 0 * * 0'  # Setiap Minggu jam 00:00 UTC

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - run: echo "Weekly cleanup task"
```

### Auto-Label Issues

```yaml
# Otomatis label issue berdasarkan konten
- uses: actions/labeler@v5
  with:
    repo-token: ${{ secrets.GITHUB_TOKEN }}
```

### Release Automation

```yaml
# Otomatis buat release saat push tag
on:
  push:
    tags: ['v*']

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: softprops/action-gh-release@v1
        with:
          generate_release_notes: true
```

### Stale Issue Cleanup

```yaml
# Tutup issues yang tidak aktif > 60 hari
- uses: actions/stale@v9
  with:
    days-before-stale: 60
    days-before-close: 7
    stale-issue-message: 'This issue has been inactive for 60 days.'
```

## Contoh: Workflow Test untuk Project Ini

Kalau ingin menambahkan CI test:

```yaml
# .github/workflows/test.yml
name: Test

on:
  push:
    branches: [main]
    paths: [scripts/**, tests/**]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r requirements.txt
      - run: cd scripts && python -m pytest ../tests/ -v
```

Ini akan menjalankan test otomatis setiap kali ada push ke main yang mengubah file Python.

## Matrix Testing

Kalau butuh test di multiple versi:

```yaml
strategy:
  matrix:
    python-version: ['3.10', '3.11', '3.12']
    os: [ubuntu-latest, macos-latest]

steps:
  - uses: actions/setup-python@v5
    with:
      python-version: ${{ matrix.python-version }}
```

## Biaya

- **Public repo**: Actions **gratis** (unlimited minutes)
- **Private repo**: 2.000 menit/bulan (free tier), kemudian $0.008/menit
- Untuk project ini (public repo), **sepenuhnya gratis**
