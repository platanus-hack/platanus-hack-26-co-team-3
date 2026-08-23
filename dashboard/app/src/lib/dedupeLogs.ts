import type { SecurityLog } from '../types'

/**
 * The gateway currently records every decision TWICE: once writing straight
 * to Mongo (`security.Log` has no Action field, so that row lands with
 * `action: null`) and once via `POST /log` to this API, which inserts into
 * the same collection. Both rows share the same instant, agent, MCP and
 * description -- they are one decision, not two.
 *
 * Until that double-write is fixed at the source (see research/ISSUES.md),
 * collapse them on read so the UI shows one row per decision. Nothing is
 * deleted; if the root cause gets fixed this becomes a no-op.
 *
 * When two rows collide, the more complete one wins (the one carrying
 * `action` / `violatedRule`), so we never lose detail by deduping.
 */
export function dedupeLogs(logs: SecurityLog[]): SecurityLog[] {
  const byDecision = new Map<string, SecurityLog>()

  for (const log of logs) {
    const key = [log.time, log.accessedBy, log.mcpId ?? '', log.description].join('|')
    const existing = byDecision.get(key)
    if (!existing || completeness(log) > completeness(existing)) {
      byDecision.set(key, log)
    }
  }

  return Array.from(byDecision.values())
}

function completeness(log: SecurityLog): number {
  return (log.action ? 1 : 0) + (log.violatedRule ? 1 : 0) + (log.mcpName ? 1 : 0)
}
