# 04 — Branches dan Strategi Branching

## Branch di Project Ini

| Branch | Isi | Siapa yang manage |
|--------|-----|-------------------|
| `main` | Kode sumber: Python, HTML, CSS, JS, workflow YAML | Kamu (push manual) |
| `dashboard-data` | Data output: JSON, enriched activities | Actions (otomatis) |

### Kenapa Dipisah?

Kalau data JSON (yang bisa ratusan KB–MB) dicampur di `main`, setiap push kode kecil akan membawa diff data besar. Dengan memisahkan:
- `main` tetap bersih — hanya perubahan kode
- `dashboard-data` menyimpan state pipeline yang terus berubah
- Deploy menggabungkan keduanya saat build

## Konsep Branch untuk Developer Solo

### Model Paling Simpel: Main Only

```
main ──●──●──●──●──●──●──  (semua langsung ke main)
```

Ini yang kamu pakai sekarang. Untuk project solo, **ini sudah cukup**. Kamu push langsung ke main, Pages deploy otomatis.

### Model dengan Feature Branch

```
main    ──●────────●──────●──
           \      / \    /
feature-a   ●──●─┘   \  /
                       \/
feature-b        ●──●──┘
```

Kapan pakai model ini:
- Kalau mau eksperimen tanpa merusak main
- Kalau fitur butuh waktu lama dan kamu mau main tetap stabil
- Kalau kerja dari banyak komputer dan perlu sinkronisasi fitur yang in-progress

### Cara Pakai Feature Branch

```bash
# Buat branch baru
git checkout -b feat/journal-page

# Kerja, commit, push
git add .
git commit -m "feat: add journal page"
git push -u origin feat/journal-page

# Setelah selesai, merge ke main
git checkout main
git pull
git merge feat/journal-page
git push

# Hapus branch
git branch -d feat/journal-page
git push origin --delete feat/journal-page
```

## Branch Protection (Opsional)

Di Settings → Branches → Branch protection rules, kamu bisa set:

| Rule | Artinya |
|------|---------|
| Require PR before merging | Tidak bisa push langsung ke main |
| Require status checks | Test harus pass sebelum merge |
| Require review | Minimal 1 reviewer (kurang relevan untuk solo) |

Untuk developer solo, ini biasanya **tidak perlu**. Tapi berguna kalau kamu mau memaksa diri sendiri untuk review sebelum merge.

## Tips

- **Jangan edit `dashboard-data` manually** — Branch ini dikelola otomatis oleh Actions
- **`git fetch --all`** — Untuk melihat semua branch remote
- **`git branch -a`** — List semua branch (lokal + remote)
- **Sinkronisasi antar komputer** — Selalu `git pull` sebelum mulai kerja di komputer yang berbeda
