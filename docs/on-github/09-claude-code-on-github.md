# 09 — Menggunakan Claude Code dengan GitHub

## Claude Code + GitHub: Workflow

Claude Code bisa berinteraksi dengan GitHub melalui `gh` CLI yang sudah terinstall. Ini memungkinkan:

### 1. Commit dan Push

```bash
# Claude Code bisa langsung commit dan push
# Biasanya lewat slash command:
/commit          # Commit dengan pesan otomatis
/commit-push     # Commit + push ke remote
```

### 2. Membuat Pull Request

```bash
# Claude Code bisa buat PR
gh pr create --title "feat: add new feature" --body "Description..."
```

### 3. Trigger Workflow

```bash
# Trigger sync dari Claude Code
gh workflow run "Sync Heatmaps" --field source=garmin
```

### 4. Cek Status

```bash
# Lihat workflow runs
gh run list --limit 5

# Lihat detail run
gh run view <run-id>

# Lihat issues
gh issue list
```

## CLAUDE.md — Instruksi untuk Claude Code

File `CLAUDE.md` di root repo adalah **instruksi permanen** untuk Claude Code. Setiap kali Claude Code membuka project ini, dia membaca CLAUDE.md.

Isinya biasanya:
- Arsitektur project
- Cara menjalankan test
- File-file penting
- Konvensi koding
- Environment variables yang diperlukan

CLAUDE.md di-commit ke repo, jadi tersinkron di semua komputer.

## GitHub Actions + Claude Code (CI/CD)

### Skenario: Claude Code di GitHub Actions

Kamu bisa menjalankan Claude Code **di dalam GitHub Actions** untuk otomasi:

```yaml
# .github/workflows/claude-review.yml (contoh)
name: Claude Code Review
on: pull_request

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Claude Code review
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          npx @anthropic-ai/claude-code --print "Review the PR changes for bugs"
```

Ini memungkinkan:
- **Auto code review** di setiap PR
- **Auto fix** lint errors
- **Generate documentation** otomatis

### Catatan Biaya

Claude Code di Actions menggunakan API key kamu (Anthropic API), jadi ada **biaya per token**. Pastikan set budget limit di Anthropic Console.

## GitHub Copilot vs Claude Code

| Aspek | GitHub Copilot | Claude Code |
|-------|---------------|-------------|
| Integrasi | Built-in di VS Code/JetBrains | CLI + VS Code extension |
| Scope | Autocomplete inline | Agent yang bisa edit multiple files, run commands |
| Context | File yang sedang dibuka | Seluruh project + terminal + web |
| GitHub integration | Deep (PR review, Actions) | Via `gh` CLI |
| Model | GPT-4o / Claude | Claude (Sonnet/Opus/Haiku) |

Keduanya bisa dipakai bersamaan. Claude Code lebih cocok untuk task yang butuh **reasoning dan multi-file changes**.

## Tips Menggunakan Claude Code dengan GitHub

1. **Selalu review sebelum push** — Claude Code bisa commit, tapi review diff-nya sebelum approve push
2. **CLAUDE.md up to date** — Update CLAUDE.md kalau arsitektur berubah, supaya Claude Code selalu punya konteks
3. **Pakai slash commands** — `/commit`, `/commit-push` lebih konsisten daripada manual
4. **Memory** — Claude Code menyimpan memory per-project. Feedback yang kamu berikan akan diingat di sesi berikutnya (di komputer yang sama)
