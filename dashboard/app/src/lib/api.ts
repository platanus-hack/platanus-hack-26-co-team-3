import type { Agent, AgentSession, ConsistencyReport, SecurityLog } from '../types'

const API_URL = import.meta.env.VITE_API_URL ?? 'https://roxygt.lat/api'
const DEMO_API_URL = import.meta.env.VITE_DEMO_API_URL ?? 'https://roxygt.lat/demo-api'

/**
 * The victim API's own verdict on its data. Returns 200 when consistent and
 * 409 when it isn't -- both are valid answers, so only a transport failure
 * or an unexpected status counts as an error here.
 */
export async function fetchConsistency(): Promise<ConsistencyReport> {
  const res = await fetch(`${DEMO_API_URL}/health/consistency`)
  if (res.status !== 200 && res.status !== 409) {
    throw new Error(`Failed to load consistency (${res.status})`)
  }
  return res.json()
}

export async function fetchSecurityLogs(): Promise<SecurityLog[]> {
  const res = await fetch(`${API_URL}/log?limit=500`)
  if (!res.ok) {
    throw new Error(`Failed to load security logs (${res.status})`)
  }
  return res.json()
}

export async function fetchSessions(): Promise<AgentSession[]> {
  const res = await fetch(`${API_URL}/sessions`)
  if (!res.ok) {
    throw new Error(`Failed to load sessions (${res.status})`)
  }
  return res.json()
}

export async function fetchSessionAgents(sessionId: string): Promise<Agent[]> {
  const res = await fetch(`${API_URL}/agents?sessionId=${encodeURIComponent(sessionId)}`)
  if (!res.ok) {
    throw new Error(`Failed to load agents (${res.status})`)
  }
  return res.json()
}
