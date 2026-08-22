# Agent config (repo-wide)

This folder ships **Superpowers** so every teammate gets the same agent skills after `git pull`. No per-person plugin install.

| Path | What it does |
|------|----------------|
| `plugins/superpowers/` | Vendored Superpowers 6.3.0 (skills + session-start hook) |
| `skills/` | Symlink to those skills so Grok loads them as project skills (no trust gate) |
| `config.toml` | Enables the plugin for Grok in this repo |
| `rules/superpowers.md` | Makes Superpowers mandatory in Grok sessions |

Claude Code picks it up from `.claude/settings.json` (local marketplace pointing at `plugins/superpowers`). Codex / Copilot / OpenClaw also see `.agents/skills` (symlink to the same files).

The first time Grok opens this repo it may ask you to trust the folder so the session-start hook can run. Skills and the mandatory rule still load even if you skip that.

Runtime scratch from Superpowers (`.superpowers/` at the repo root) is gitignored.
