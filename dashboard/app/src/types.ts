export type LogStatus = 'approved' | 'denied'

export interface ViolatedRule {
  priority: number
  instruction: string
}

export interface SecurityLog {
  _id: string
  status: LogStatus
  mcpId: string | null
  mcpName: string | null
  time: string
  accessedBy: string
  action: string | null
  violatedRule: ViolatedRule | null
  description: string
}

// `outcome` is null until something (agent-flow, or a PATCH /agents/{id})
// records a verdict for that node -- absence means "no verdict yet", not
// "succeeded".
export type AgentOutcome = 'ok' | 'denied' | 'error'

export interface Agent {
  _id: string
  purpose: string
  parentId: string | null
  sessionId: string
  outcome: AgentOutcome | null
}

export interface AgentSession {
  sessionId: string
  rootPurpose: string
  agentCount: number
  startedAt: string
  outcome: AgentOutcome | null
}
