# 10 — Batasan GitHub Pages dan Kapan Butuh Lebih

## Batasan Utama GitHub Pages

### 1. Tidak Ada Server-Side Code

GitHub Pages hanya serve file statis. Tidak bisa:
- Menjalankan Python, Node.js, atau bahasa server-side lainnya
- Menerima dan memproses form submission
- Mengakses database
- Melakukan server-side authentication
- Membuat API endpoint

### 2. Tidak Ada User Authentication

Siapapun yang punya URL bisa mengakses site kamu. Tidak ada cara untuk:
- Memproteksi halaman dengan login
- Membedakan user A dan user B
- Menyimpan data per-user di server

### 3. Tidak Ada Dynamic Data dari Server

Data hanya bisa berubah kalau:
- Pipeline Python generate JSON baru (via Actions)
- JavaScript di browser membaca dari localStorage (per-user, per-browser)
- JavaScript fetch ke API **eksternal** (misal Firebase, Supabase)

### 4. Tidak Ada File Upload ke Server

User tidak bisa upload file yang disimpan di server. Fitur import JSON di Journal/Todos hanya membaca file ke localStorage browser.

## Kapan Perlu Sistem Eksternal?

| Kebutuhan | GitHub Pages Cukup? | Solusi |
|-----------|---------------------|--------|
| Dashboard read-only | Ya | Sudah ada |
| Catatan personal (satu device) | Ya | localStorage (sudah ada) |
| Catatan sync antar device | **Tidak** | Firebase/Supabase |
| Login/authentication | **Tidak** | Auth0, Firebase Auth |
| Form submission | **Tidak** | Formspree, Google Forms |
| Real-time data | **Tidak** | WebSocket via external service |
| File storage (gambar, PDF) | **Tidak** | S3, Cloudflare R2 |
| API endpoint | **Tidak** | Vercel/Netlify Functions, AWS Lambda |

## Opsi Upgrade

### Level 1: GitHub Pages + External Service (Tanpa Migrasi)

Tetap pakai GitHub Pages, tapi tambahkan service eksternal yang dipanggil dari JavaScript:

**Firebase Firestore** (gratis sampai 1 GB):
```javascript
// Di journal.html, ganti localStorage dengan Firebase
import { getFirestore, collection, addDoc } from "firebase/firestore";
const db = getFirestore(app);
await addDoc(collection(db, "journal"), { title: "...", body: "..." });
```

Keuntungan: Site tetap di GitHub Pages, data sync antar device.

### Level 2: Vercel / Netlify (Migrasi Ringan)

Pindah hosting ke platform yang mendukung serverless functions:

**Vercel** (free tier):
- Deploy dari GitHub repo (otomatis)
- Support Next.js, Python (serverless functions)
- Bisa punya API routes (`/api/journal`)
- Database: Vercel Postgres (free tier)

```
site/ → deploy sebagai static files
api/  → serverless functions (Python atau Node.js)
```

**Netlify** (free tier):
- Mirip Vercel
- Netlify Functions (AWS Lambda di belakang layar)
- Netlify Forms (tangkap form submission tanpa backend)

### Level 3: Full Backend (Migrasi Besar)

Kalau butuh full control:

**Next.js + Vercel**:
```bash
npx create-next-app@latest
# Deploy ke Vercel
# Punya API routes, SSR, database access
```

**Python + Railway/Render**:
```bash
# Flask/FastAPI backend
# Deploy ke Railway (free tier)
# Connect ke PostgreSQL yang sudah ada
```

## Perbandingan Platform

| Platform | Static | Functions | DB | Auth | Free Tier | Effort Migrasi |
|----------|--------|-----------|-----|------|-----------|----------------|
| GitHub Pages | Ya | Tidak | Tidak | Tidak | Unlimited | — (sudah) |
| Vercel | Ya | Ya | Ya | Opsional | Generous | Rendah |
| Netlify | Ya | Ya | Opsional | Opsional | Generous | Rendah |
| Railway | Ya | Ya | Ya | Build sendiri | $5 credit/bulan | Sedang |
| AWS (S3+Lambda) | Ya | Ya | Ya | Cognito | Free tier 12 bulan | Tinggi |

## Rekomendasi untuk Project Ini

**Saat ini**: GitHub Pages sudah cukup. Dashboard read-only + localStorage untuk Journal/Todo memenuhi kebutuhan.

**Kalau nanti butuh sync data antar device**: Tambahkan Firebase Firestore (Level 1) — minimal effort, tidak perlu migrasi.

**Kalau nanti butuh API/backend**: Pindah ke Vercel (Level 2) — bisa deploy Next.js dari repo yang sama, gratis.

Prinsipnya: **Jangan over-engineer**. Upgrade hanya kalau ada kebutuhan nyata, bukan "just in case".
