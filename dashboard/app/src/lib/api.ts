import type { SecurityLog } from '../types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function fetchSecurityLogs(): Promise<SecurityLog[]> {
  const res = await fetch(`${API_URL}/security-logs?limit=500`)
  if (!res.ok) {
    throw new Error(`Failed to load security logs (${res.status})`)
  }
  return res.json()
}
