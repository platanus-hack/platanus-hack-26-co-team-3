import type { SecurityLog } from '../types'

const API_URL = import.meta.env.VITE_API_URL ?? 'https://roxygt.lat/api'

export async function fetchSecurityLogs(): Promise<SecurityLog[]> {
  const res = await fetch(`${API_URL}/security-logs?limit=500`)
  if (!res.ok) {
    throw new Error(`Failed to load security logs (${res.status})`)
  }
  return res.json()
}
