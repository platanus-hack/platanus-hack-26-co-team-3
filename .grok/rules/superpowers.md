# Superpowers is required

This repository vendors Superpowers. Use it in every agent session.

Skills live in `.grok/plugins/superpowers/skills/`.

## Mandatory bootstrap

At the start of a conversation, follow `using-superpowers` before answering or acting.

If there is even a small chance a Superpowers skill applies, read that skill's `SKILL.md` and follow it. Do not skip this because the task looks small.

## When to use which skill

| Situation | Skill |
|-----------|--------|
| Starting any conversation / checking which skills apply | `using-superpowers` |
| New feature, design, or behavior change | `brainstorming` first |
| Bug, test failure, unexpected behavior | `systematic-debugging` |
| Implementing a feature or bugfix | `test-driven-development` |
| Multi-step implementation after a spec | `writing-plans`, then `subagent-driven-development` or `executing-plans` |
| About to claim done / fixed / passing | `verification-before-completion` |
| Isolated git workspace for feature work | `using-git-worktrees` |
| Ready to merge or open a PR | `requesting-code-review`, then `finishing-a-development-branch` |

User instructions in `CLAUDE.md` (block isolation) take precedence over Superpowers when they conflict.

Do not copy Superpowers skills into a work-block folder. They stay at repo root under `.grok/plugins/superpowers/`.
