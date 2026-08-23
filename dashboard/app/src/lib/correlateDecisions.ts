import type { Agent, AgentOutcome, SecurityLog } from '../types'
import { parseApiTime } from './time'

/**
 * Ties Roxy's decisions (the `security` collection) to the agents that
 * triggered them (the `agents` collection).
 *
 * Those two collections have no shared key today: the gateway receives the
 * agent id in `X-Roxy-Agent-Run` but never persists it on the log (see
 * research/ISSUES.md). Until it does, the only honest link is the invoice
 * both sides name -- the agent's purpose reads
 * "Conciliar INV-1005: ..." and the log's accessedBy reads
 * "agent-subtask-INV-1005".
 *
 * This is a correlation, not a foreign key, so it is deliberately strict:
 *   - the invoice id must match exactly on both sides
 *   - the decision must fall inside the run's own time window
 * Anything that does not clear both bars is left uncorrelated (outcome
 * stays null = "no verdict recorded") rather than guessed. A demo that
 * shows a decision on the wrong agent is worse than one that shows none.
 */

const INVOICE_RE = /\bINV-\d+\b/

/** Agent ids are ObjectIds; their first 4 bytes are the creation timestamp. */
function objectIdTime(id: string): number | null {
  if (!/^[0-9a-f]{24}$/i.test(id)) return null
  return parseInt(id.slice(0, 8), 16) * 1000
}

function invoiceOf(text: string | null | undefined): string | null {
  return text ? (text.match(INVOICE_RE)?.[0] ?? null) : null
}

export interface DecisionsByAgent {
  outcomeFor: (agentId: string) => AgentOutcome | null
  logsFor: (agentId: string) => SecurityLog[]
}

/** Extra slack after the last agent was registered, for decisions still in flight. */
const TRAILING_WINDOW_MS = 3 * 60 * 1000
/** Clock skew allowance before the first agent. */
const LEADING_WINDOW_MS = 30 * 1000

export function correlateDecisions(agents: Agent[], logs: SecurityLog[]): DecisionsByAgent {
  const times = agents.map((a) => objectIdTime(a._id)).filter((t): t is number => t !== null)
  const byAgent = new Map<string, SecurityLog[]>()

  if (times.length > 0) {
    const from = Math.min(...times) - LEADING_WINDOW_MS
    const to = Math.max(...times) + TRAILING_WINDOW_MS

    // One invoice can be handled by only one agent per run, so this stays 1:1.
    const agentByInvoice = new Map<string, Agent>()
    for (const agent of agents) {
      const invoice = invoiceOf(agent.purpose)
      // Delegation nodes name several invoices; only leaves own exactly one.
      if (invoice && !agentByInvoice.has(invoice) && !agent.purpose.startsWith('Delegar')) {
        agentByInvoice.set(invoice, agent)
      }
    }

    for (const log of logs) {
      const at = parseApiTime(log.time)
      if (Number.isNaN(at) || at < from || at > to) continue

      const invoice = invoiceOf(log.accessedBy)
      if (!invoice) continue

      const agent = agentByInvoice.get(invoice)
      if (!agent) continue

      const bucket = byAgent.get(agent._id) ?? []
      bucket.push(log)
      byAgent.set(agent._id, bucket)
    }
  }

  return {
    outcomeFor(agentId) {
      const found = byAgent.get(agentId)
      if (!found || found.length === 0) return null
      return found.some((l) => l.status === 'denied') ? 'denied' : 'ok'
    },
    logsFor(agentId) {
      return byAgent.get(agentId) ?? []
    },
  }
}

/**
 * Returns the agents with their outcome filled in from correlated decisions.
 * An outcome already stored on the agent always wins -- once something
 * actually records one, this correlation stops guessing for that node.
 */
export function withCorrelatedOutcomes(agents: Agent[], logs: SecurityLog[]): Agent[] {
  const decisions = correlateDecisions(agents, logs)
  return agents.map((agent) =>
    agent.outcome ? agent : { ...agent, outcome: decisions.outcomeFor(agent._id) },
  )
}
