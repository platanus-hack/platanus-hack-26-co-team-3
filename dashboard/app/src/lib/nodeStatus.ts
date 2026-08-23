import type { AgentOutcome } from '../types'

export interface OutcomeTokens {
  label: string
  color: string
  bg: string
  border: string
}

export function outcomeTokens(outcome: AgentOutcome | null): OutcomeTokens {
  if (outcome === 'error') {
    return { label: 'Error', color: 'var(--red)', bg: 'var(--red-bg)', border: 'var(--red-border)' }
  }
  if (outcome === 'denied') {
    return { label: 'Denied by Roxy', color: 'var(--accent)', bg: 'var(--accent-bg)', border: 'var(--accent-border)' }
  }
  if (outcome === 'ok') {
    return { label: 'OK', color: 'var(--green)', bg: 'var(--green-bg)', border: 'var(--green-border)' }
  }
  return { label: 'No verdict', color: 'var(--text-muted)', bg: 'var(--panel)', border: 'var(--border)' }
}
