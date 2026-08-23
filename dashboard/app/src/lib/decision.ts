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

/**
 * The engine writes its reason in English, in its own vocabulary
 * ("operation 2 (write on 'invoices') is denied by rule priority 1"). Nobody
 * watching the demo should have to decode that. Split it into the two
 * questions a person actually asks: what did the agent try, and what did Roxy
 * do about it.
 */

const OP_PARTS_RE = /^([a-z/]+)\s+on\s+'([^']+)'$/i

/** The engine's operation verbs, as they appear in `operation (...)`. */
const VERBS: Record<string, string> = {
  read: 'Leer',
  write: 'Escribir en',
  'write/destructive': 'Escribir o borrar en',
  destructive: 'Borrar en',
}

export interface DecisionExplanation {
  /** What the agent tried to do, in Spanish. Null when it can't be read. */
  attempt: string | null
  /** What Roxy decided, in Spanish. */
  verdict: string
}

export function explainDecision(log: SecurityLog): DecisionExplanation {
  const facts = decisionFacts(log)
  const parts = facts.operation?.match(OP_PARTS_RE)

  let attempt: string | null = null
  if (parts) {
    const verb = VERBS[parts[1].toLowerCase()] ?? parts[1]
    attempt = `${verb} ${parts[2]}`
  } else if (log.action) {
    attempt = `Ejecutar ${log.action}`
  }

  const denied = log.status === 'denied'
  const verdict = denied
    ? facts.rulePriority !== null
      ? `Bloqueado por la regla ${facts.rulePriority}`
      : 'Bloqueado'
    : 'Permitido — ninguna regla lo impide'

  return { attempt, verdict }
}

/** Free-text match across the fields someone would actually search by. */
export function logMatches(log: SecurityLog, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return [log.accessedBy, log.mcpName, log.action, log.description]
    .some((f) => f?.toLowerCase().includes(q))
}
