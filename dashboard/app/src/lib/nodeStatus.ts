import type { AgentOutcome } from '../types'

export interface OutcomeTokens {
  label: string
  color: string
  bg: string
  border: string
}

export function outcomeTokens(outcome: AgentOutcome | null): OutcomeTokens {
  if (outcome === 'error') {
    return { label: 'Falló', color: 'var(--red)', bg: 'var(--red-bg)', border: 'var(--red-border)' }
  }
  if (outcome === 'denied') {
    return { label: 'Bloqueado por Roxy', color: 'var(--held)', bg: 'var(--held-bg)', border: 'var(--held-border)' }
  }
  if (outcome === 'ok') {
    return { label: 'OK', color: 'var(--green)', bg: 'var(--green-bg)', border: 'var(--green-border)' }
  }
  return { label: 'Sin veredicto', color: 'var(--text-muted)', bg: 'var(--panel)', border: 'var(--border)' }
}
