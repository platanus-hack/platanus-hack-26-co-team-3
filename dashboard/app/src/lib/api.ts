import type { Agent, AgentSession, SecurityLog } from '../types'

const API_URL = import.meta.env.VITE_API_URL ?? 'https://roxygt.lat/api'

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
