import type { LogStatus } from '../types'

export interface StatusTokens {
  label: string
  color: string
  bg: string
  border: string
}

export function statusTokens(status: LogStatus): StatusTokens {
  const isDenied = status === 'denied'
  return {
    label: isDenied ? 'Bloqueada' : 'Aprobada',
    color: isDenied ? 'var(--red)' : 'var(--green)',
    bg: isDenied ? 'var(--red-bg)' : 'var(--green-bg)',
    border: isDenied ? 'var(--red-border)' : 'var(--green-border)',
  }
}
