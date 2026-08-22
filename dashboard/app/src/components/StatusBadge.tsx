import type { LogStatus } from '../types'
import { statusTokens } from '../lib/status'

export function StatusBadge({ status }: { status: LogStatus }) {
  const tokens = statusTokens(status)
  return (
    <span
      className="status-badge"
      style={{ background: tokens.bg, color: tokens.color, borderColor: tokens.border }}
    >
      <span className="status-dot" style={{ background: tokens.color }} />
      {tokens.label}
    </span>
  )
}
