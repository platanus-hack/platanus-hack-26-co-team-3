import type { MouseEvent } from 'react'
import type { SecurityLog } from '../types'
import { formatFullTime } from '../lib/format'
import { statusTokens } from '../lib/status'
import { CloseIcon } from './icons'

interface LogDrawerProps {
  log: SecurityLog | null
  onClose: () => void
}

export function LogDrawer({ log, onClose }: LogDrawerProps) {
  if (!log) return null
  const tokens = statusTokens(log.status)

  function stopClick(e: MouseEvent) {
    e.stopPropagation()
  }

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={stopClick}>
        <div className="drawer-header">
          <span
            className="status-badge"
            style={{ background: tokens.bg, color: tokens.color, borderColor: tokens.border }}
          >
            {tokens.label}
          </span>
          <button type="button" className="close-btn" aria-label="Close" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>

        <div className="drawer-title">{log.mcpName ?? 'Unknown MCP'}</div>

        <div className="drawer-fields">
          <div className="drawer-field">
            <div className="drawer-field-label">Accessed by</div>
            <div className="drawer-field-value mono">{log.accessedBy}</div>
          </div>
          <div className="drawer-field">
            <div className="drawer-field-label">Time</div>
            <div className="drawer-field-value">{formatFullTime(log.time)}</div>
          </div>
          <div className="drawer-field">
            <div className="drawer-field-label">MCP ID</div>
            <div className="drawer-field-value mono muted">{log.mcpId}</div>
          </div>
          <div className="drawer-field">
            <div className="drawer-field-label">Description</div>
            <div className="drawer-field-value">{log.description}</div>
          </div>
        </div>
      </div>
    </div>
  )
}
