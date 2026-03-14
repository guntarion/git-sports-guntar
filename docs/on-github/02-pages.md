# 02 — GitHub Pages

## Apa Itu GitHub Pages?

Hosting website **statis gratis** dari GitHub. Kamu taruh file HTML/CSS/JS di repo, GitHub serve ke internet dengan HTTPS.

URL: `https://{username}.github.io/{repo-name}/`

Untuk project ini: `https://guntarion.github.io/git-sports-guntar/`

## Apa yang Bisa dan Tidak Bisa

### Bisa
- Serve file HTML, CSS, JS, gambar, JSON, font
- HTTPS otomatis (gratis)
- Custom domain (misal `dashboard.mydomain.com`)
- Single Page App (SPA) — tapi perlu workaround untuk routing

### Tidak Bisa
- Menjalankan server-side code (Python, Node.js, PHP)
- Menerima POST request atau form submission ke server
- Mengakses database langsung
- Menjalankan cron job (itu tugas Actions)
- File storage yang bisa diwrite oleh pengunjung

## Cara Deploy di Project Ini

Ada **dua mode** deploy GitHub Pages:

### Mode 1: Deploy dari Branch (sederhana)
Setting → Pages → Source → "Deploy from a branch" → pilih `main` / `docs`

### Mode 2: Deploy dari Actions (project ini pakai ini)
Setting → Pages → Source → "GitHub Actions"

Kenapa pakai Actions? Karena kita perlu **menggabungkan** file dari dua branch:
- `main` → HTML, CSS, JS (kode UI)
- `dashboard-data` → data.json, activities.json (output pipeline)

File `pages.yml` melakukan ini:
```
1. Checkout main (ambil HTML)
2. Checkout dashboard-data (ambil JSON data)
3. Gabungkan di folder site/
4. Upload & deploy
```

## Batasan GitHub Pages

| Batasan | Detail |
|---------|--------|
| Ukuran site | Maks 1 GB |
| Bandwidth | 100 GB/bulan (soft limit) |
| Build | 10 builds/jam |
| File | Maks 100 MB per file |
| Repository | Harus publik (free tier) atau private (Pro/Team) |

## URL Routing

GitHub Pages tidak punya server-side routing. Jadi:

```
✅ /index.html          → bisa
✅ /journal.html         → bisa
✅ /todos.html           → bisa

❌ /journal              → 404! (tanpa .html)
❌ /api/data             → 404! (tidak ada server)
```

Kalau pakai framework seperti Next.js dengan static export, perlu configure `trailingSlash` dan/atau `404.html` hack.

## Custom Domain (Opsional)

1. Beli domain (misal di Namecheap, Cloudflare)
2. Settings → Pages → Custom domain → masukkan domain
3. Tambah DNS record:
   - CNAME: `www` → `guntarion.github.io`
   - A records: IP GitHub Pages
4. GitHub otomatis provision SSL certificate

## Tips

- **Cache**: GitHub Pages di-cache oleh CDN. Setelah deploy, mungkin perlu Cmd+Shift+R untuk lihat perubahan
- **`__APP_VERSION__`**: Di project ini, placeholder di `index.html` di-replace dengan commit SHA saat deploy, jadi browser tahu kapan harus refresh cache
- **404.html**: Kalau kamu taruh file `404.html` di root, GitHub Pages akan serve itu untuk URL yang tidak ditemukan
