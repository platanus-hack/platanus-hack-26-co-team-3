import type { SecurityLog } from '../types'

/**
 * The gateway leaves `violatedRule` null on denials today (see
 * research/ISSUES.md) -- the only place the governing rule survives is
 * inside the description text the engine writes:
 *
 *   "operation 1 (write/destructive on 'orders') is denied by rule priority 1"
 *
 * Pulling the pieces back out lets the table show *why* at a glance instead
 * of making everyone open a drawer and read a sentence. When the gateway
 * starts populating violatedRule properly, that wins over anything parsed
 * here.
 */

const RULE_RE = /rule priority (\d+)/i
const OP_RE = /operation\s+\d+\s+\(([^)]+)\)/i

export interface DecisionFacts {
  /** Priority of the rule that governed, when it can be established. */
  rulePriority: number | null
  /** e.g. "write/destructive on 'orders'" -- what the agent tried to do. */
  operation: string | null
}

export function decisionFacts(log: SecurityLog): DecisionFacts {
  if (log.violatedRule) {
    return {
      rulePriority: log.violatedRule.priority,
      operation: log.description.match(OP_RE)?.[1] ?? null,
    }
  }
  const priority = log.description.match(RULE_RE)?.[1]
  return {
    rulePriority: priority ? Number(priority) : null,
    operation: log.description.match(OP_RE)?.[1] ?? null,
  }
}

/** Free-text match across the fields someone would actually search by. */
export function logMatches(log: SecurityLog, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return [log.accessedBy, log.mcpName, log.action, log.description]
    .some((f) => f?.toLowerCase().includes(q))
}
