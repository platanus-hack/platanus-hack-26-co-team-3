# CLAUDE.md — Roxy Monorepo Rules

This repository is organized as a set of **independent work blocks**, as defined in
[idea.md](idea.md). Each block is a self-contained unit of work assigned to one
person, and each block lives in its **own folder**. These rules govern how Claude
must work within this repo.

## Blocks → Folders

| # | Block (from idea.md)                                              | Owner    | Folder                  |
|---|----------------------------------------------------------------------|----------|--------------------------|
| 1 | Datos de Mongo (schema y mock)                                       | Santiago | `mongo-data/`            |
| 2 | Roxy Gateway — API/MCP de agente                                     | Stiven   | `roxy-gateway/`          |
| 3 | Dashboard (full stack web)                                           | Santiago | `dashboard/`             |
| 4 | API funcional de demo con datos en Mongodb                           | Freddy   | `demo-api/`              |
| 5 | Langchain/Other flujo de agentes para demo                           | Andres   | `agent-flow-demo/`       |
| 6 | Investigación                                                        | Freddy   | `research/`              |
| 7 | Demo interactivo                                                     | Todos    | `demo/`                  |
| 8 | Landing Page                                                         | Freddy   | `landing-page/`          |
| 9 | Langchain interceptor class (trace de nodos → DB)                    | Santiago | `langchain-interceptor/` |

Root-level files (`README.md`, `idea.md`, `project-description.md`,
`platanus-hack-project.jsonc`, `project-logo.png`) are project metadata, not part
of any block. Only touch them when the user explicitly asks about project-level
metadata, docs, or submission requirements — not as a side effect of block work.

## Hard Isolation Rule

When a request maps to a given block, **all work stays inside that block's
folder**, and nothing else in the repo is read, referenced, imported from, or
used as a basis for the implementation.

Concretely, when working on a block:

- **Do not** implement, edit, or generate code for any other block, even if it
  seems related or convenient to bundle in.
- **Do not** read other blocks' folders to "borrow" patterns, types, schemas, or
  conventions unless the user explicitly says to integrate across blocks. Each
  block's folder must be able to stand alone.
- **Do not** add imports, API calls, or dependencies that reach into another
  block's folder (e.g. a `dashboard/` component importing something from
  `roxy-gateway/`). If two blocks genuinely need to talk to each other, they do
  so at runtime through their own defined interface (HTTP, MCP, DB), never via
  shared source code.
- **Do not** create shared/common folders (`shared/`, `lib/`, `common/`, etc.) to
  reuse code between blocks unless the user explicitly asks for that. Prefer
  small duplication over cross-block coupling.
- If the folder for a block doesn't exist yet, create it and do the work inside
  it — don't scatter files at the repo root or inside another block's folder.

The only exception to reading another block's folder is when the user
**explicitly** names the other block/folder and asks to read from it — e.g.
"read file x from `roxy-gateway/`" or "check how block 2 defines its schema".
In that case, reading is allowed, but it must stay read-only reference: unless
the user also explicitly asks for it, do not copy, import, or base the current
block's implementation on what was read. Never read another block's folder on
your own inference that it might be "related" or "useful context" — only do it
when asked to, by name.

### Example

If asked to "create a dashboard UI", work exclusively inside `dashboard/`:
build the dashboard's own frontend/API code there. Do not implement or modify
`roxy-gateway/`, `demo-api/`, `mongo-data/`, etc., and do not read those folders
to inform the dashboard's implementation — only the dashboard block's own
requirements (block 3 in idea.md) apply.

## Exceptions (explicitly cross-block by design)

- **Block 7 — `demo/`**: exists to run/showcase the other blocks together (API
  normal → API after agentic process without Roxy → with Roxy, viewing the
  dashboard each time). It may contain orchestration scripts, run instructions,
  or config that references how to start other blocks' services, but it must
  **not** contain application logic that belongs to another block. Treat it as
  a thin runner/README layer, not a place to reimplement functionality.
- **Block 6 — `research/`**: documentation/research only (industry A2A,
  incidents, existing solutions, market impact). No application code.
- **Block 8 — `landing-page/`**: standalone marketing site, no coupling to
  other blocks' code.

If a request seems to require touching more than one block's folder outside of
these exceptions, stop and ask the user which block it belongs to, or whether
they intend a genuine cross-block integration change (which should be called
out explicitly, not assumed).

## Superpowers (required)

This repo vendors [Superpowers](https://github.com/obra/superpowers) at
`.grok/plugins/superpowers`. After `git pull`, Grok and Claude Code load it
without a personal plugin install. Treat it as mandatory.

- At the start of every conversation, follow `using-superpowers` before acting.
- If a Superpowers skill applies (brainstorming, TDD, debugging, planning,
  review, verification), read that skill's `SKILL.md` and follow it.
- Skills: `.grok/plugins/superpowers/skills/`
- Grok: enabled by `.grok/config.toml`. Rules: `.grok/rules/superpowers.md`.
- Claude Code: enabled by `.claude/settings.json` (local marketplace).

Block isolation in this file still wins if it conflicts with a Superpowers
workflow (for example: do not read or edit another block's folder).
